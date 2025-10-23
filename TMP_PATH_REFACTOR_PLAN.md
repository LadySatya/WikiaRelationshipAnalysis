# tmp_path Fixture Refactoring Plan

## Problem Statement

Unit tests are currently creating real directories in `data/projects/` which pollutes the project data directory with test artifacts:
- `naruto_wiki/`, `avatar_wiki/`, `bleach_wiki/`, `test_wiki/`, `test_project/`
- These persist after tests and contain old `raw/` folders from before cleanup

**Root Cause:** Components create directories during `__init__()` before mocking takes effect:
- `VectorStore.__init__()` → `persist_path.mkdir(parents=True, exist_ok=True)`
- `WikiaCrawler.__init__()` → creates project directory structure
- `CharacterExtractor.__init__()` → initializes QueryEngine which creates VectorStore

## Goal

Isolate all test file I/O to temporary directories using pytest's `tmp_path` fixture, ensuring:
- ✅ No pollution of `data/projects/` directory
- ✅ Automatic cleanup after test completion
- ✅ Test isolation (each test gets fresh environment)
- ✅ All tests continue to pass

---

## Current Test Architecture

### Files Needing Changes (Estimated ~75 tests)

#### 1. **VectorStore Tests** (`test_vector_store.py`)
- **Lines affected:** ~30 test methods
- **Current pattern:**
  ```python
  store = VectorStore(project_name="test_wiki")  # Creates data/projects/test_wiki/
  ```
- **Issue:** Even with mocked ChromaDB, `mkdir()` still executes

#### 2. **VectorStore Integration Tests** (`test_vector_store_integration.py`)
- **Lines affected:** ~5 test methods
- **Current pattern:**
  ```python
  @pytest.fixture
  def temp_vector_store_dir():
      temp_dir = tempfile.mkdtemp()  # Already using temp dirs!
      yield temp_dir
      shutil.rmtree(temp_dir, ignore_errors=True)
  ```
- **Issue:** Already using temp dirs, but could use pytest's `tmp_path` for consistency

#### 3. **RAGRetriever Tests** (`test_retriever.py`)
- **Lines affected:** ~12 test methods
- **Current pattern:**
  ```python
  retriever = RAGRetriever(project_name="test_wiki")
  # Creates VectorStore which creates data/projects/test_wiki/
  ```

#### 4. **QueryEngine Tests** (`test_query_engine.py`)
- **Lines affected:** ~10 test methods
- **Current pattern:**
  ```python
  engine = QueryEngine(project_name="test_wiki")
  # Creates RAGRetriever -> VectorStore -> directory
  ```

#### 5. **CharacterExtractor Tests** (`test_character_extractor.py`)
- **Lines affected:** ~20 test methods
- **Current pattern:**
  ```python
  extractor = CharacterExtractor(project_name="test_project")
  # Creates QueryEngine -> RAGRetriever -> VectorStore -> directory
  ```

#### 6. **WikiaCrawler Tests** (`test_crawler_init.py`)
- **Lines affected:** ~10 test methods
- **Current pattern:**
  ```python
  crawler = WikiaCrawler("test_project", config)
  # Creates project directory structure
  ```

---

## Proposed Solutions (3 Options)

### **Option A: Global Monkeypatch in conftest.py** ⭐ RECOMMENDED

**Strategy:** Intercept directory creation at the source - patch `Path.mkdir()` to redirect to temp directories.

**Implementation:**
```python
# tests/conftest.py

@pytest.fixture(autouse=True)
def isolate_data_directory(tmp_path, monkeypatch):
    """
    Automatically redirect all data/projects/ directory creation to tmp_path.

    This fixture runs for every test and ensures test isolation without
    requiring changes to individual test files.
    """
    # Create temp structure: tmp_path/data/projects/
    temp_data_dir = tmp_path / "data" / "projects"
    temp_data_dir.mkdir(parents=True, exist_ok=True)

    # Store original Path class
    from pathlib import Path as OriginalPath

    # Define wrapper that redirects specific paths
    class TestPath(type(OriginalPath())):
        def __new__(cls, *args, **kwargs):
            path_str = str(args[0]) if args else ""

            # Redirect data/projects to temp directory
            if "data/projects" in path_str or "data\\projects" in path_str:
                # Replace data/projects with temp path
                redirected = path_str.replace("data/projects", str(temp_data_dir))
                redirected = redirected.replace("data\\projects", str(temp_data_dir))
                return OriginalPath(redirected)

            return OriginalPath(*args, **kwargs)

    # Patch Path in all relevant modules
    monkeypatch.setattr("src.processor.rag.vector_store.Path", TestPath)
    monkeypatch.setattr("src.processor.analysis.character_extractor.Path", TestPath)
    monkeypatch.setattr("src.crawler.core.crawler.Path", TestPath)
```

**Pros:**
- ✅ Zero changes to test files
- ✅ Automatic for all tests (autouse=True)
- ✅ Centralized in one place
- ✅ Easy to maintain

**Cons:**
- ❌ Magic behavior (less explicit)
- ❌ Might redirect unintended paths
- ❌ Debugging harder if path logic is complex

---

### **Option B: Explicit tmp_path Parameter**

**Strategy:** Pass `tmp_path` to every component that creates directories.

**Implementation:**
```python
# Example test change
def test_vector_store_init(tmp_path):
    """VectorStore initializes correctly."""
    persist_dir = tmp_path / "data" / "projects"
    persist_dir.mkdir(parents=True)

    store = VectorStore(
        project_name="test_wiki",
        persist_directory=str(persist_dir)  # Explicitly pass temp path
    )

    assert store.project_name == "test_wiki"
```

**Changes needed:**
- Update ~75 test methods to accept `tmp_path` parameter
- Add `persist_directory=tmp_path` to every VectorStore creation
- Similar for WikiaCrawler, CharacterExtractor

**Pros:**
- ✅ Explicit and clear
- ✅ Each test controls its own paths
- ✅ No magic behavior

**Cons:**
- ❌ Requires changing ~75 test methods
- ❌ Repetitive code (boilerplate in every test)
- ❌ Easy to forget in new tests
- ❌ Time-consuming to implement

---

### **Option C: Fixture Factory Pattern**

**Strategy:** Create factory fixtures that return pre-configured instances with tmp_path.

**Implementation:**
```python
# tests/conftest.py

@pytest.fixture
def vector_store_factory(tmp_path):
    """Factory for creating VectorStore instances with isolated storage."""
    def _create_store(project_name="test_wiki"):
        persist_dir = tmp_path / "data" / "projects"
        persist_dir.mkdir(parents=True, exist_ok=True)
        return VectorStore(
            project_name=project_name,
            persist_directory=str(persist_dir)
        )
    return _create_store

@pytest.fixture
def character_extractor_factory(tmp_path, monkeypatch):
    """Factory for creating CharacterExtractor with isolated storage."""
    def _create_extractor(project_name="test_project", **kwargs):
        # Redirect data/projects to tmp_path
        persist_dir = tmp_path / "data" / "projects"
        monkeypatch.setattr(
            "src.processor.analysis.character_extractor.Path",
            lambda x: persist_dir / project_name if "data/projects" in str(x) else Path(x)
        )
        return CharacterExtractor(project_name=project_name, **kwargs)
    return _create_extractor

# Example test change
def test_vector_store_init(vector_store_factory):
    """VectorStore initializes correctly."""
    store = vector_store_factory("test_wiki")
    assert store.project_name == "test_wiki"
```

**Pros:**
- ✅ Cleaner test code (no path management in tests)
- ✅ Reusable factories
- ✅ Explicit (use factory = temp, don't use factory = real)

**Cons:**
- ❌ Still requires changing ~75 tests
- ❌ Need to create factory for every component
- ❌ More fixtures to maintain

---

## Recommended Approach: **Hybrid (A + Cleanup)**

Use **Option A** (global monkeypatch) for simplicity, plus add a cleanup fixture to catch any missed cases:

```python
# tests/conftest.py

@pytest.fixture(autouse=True)
def isolate_data_directory(tmp_path, monkeypatch):
    """Redirect data/projects to tmp_path for all tests."""
    temp_data_dir = tmp_path / "data" / "projects"
    temp_data_dir.mkdir(parents=True, exist_ok=True)

    # Store original for restoration
    original_path_class = Path

    # Create path wrapper
    def patched_path(*args, **kwargs):
        path_str = str(args[0]) if args else ""
        if "data/projects" in path_str or "data\\projects" in path_str:
            # Redirect to temp
            redirected = path_str.replace("data/projects", str(temp_data_dir))
            redirected = redirected.replace("data\\projects", str(temp_data_dir))
            return original_path_class(redirected)
        return original_path_class(*args, **kwargs)

    # Patch in all modules
    monkeypatch.setattr("src.processor.rag.vector_store.Path", patched_path)
    monkeypatch.setattr("src.processor.analysis.character_extractor.Path", patched_path)
    monkeypatch.setattr("src.crawler.core.crawler.Path", patched_path)

    yield

    # Cleanup: Remove any test projects that leaked through
    import shutil
    test_projects = ["naruto_wiki", "avatar_wiki", "test_wiki", "test_project", "bleach_wiki", "integration_test"]
    for proj in test_projects:
        proj_path = Path("data/projects") / proj
        if proj_path.exists():
            shutil.rmtree(proj_path, ignore_errors=True)


@pytest.fixture(autouse=True, scope="session")
def cleanup_test_data():
    """Session-level cleanup of any leaked test data."""
    yield
    # After all tests complete
    import shutil
    from pathlib import Path

    test_projects = ["naruto_wiki", "avatar_wiki", "test_wiki", "test_project", "bleach_wiki", "integration_test"]
    for proj in test_projects:
        proj_path = Path("data/projects") / proj
        if proj_path.exists():
            shutil.rmtree(proj_path, ignore_errors=True)
```

---

## Implementation Plan

### Phase 1: Setup (15 min)
1. ✅ Commit current work (DONE)
2. ⬜ Add `isolate_data_directory` fixture to `conftest.py`
3. ⬜ Add `cleanup_test_data` fixture to `conftest.py`

### Phase 2: Test & Verify (20 min)
1. ⬜ Run unit tests: `pytest -m unit -v`
2. ⬜ Check for leaked directories: `ls data/projects/`
3. ⬜ Debug any failures from path redirection
4. ⬜ Adjust fixture if needed (handle edge cases)

### Phase 3: Clean Existing Pollution (1 min)
1. ⬜ Delete test project folders:
   ```bash
   rm -rf data/projects/{naruto_wiki,avatar_wiki,bleach_wiki,test_project,test_wiki,integration_test}
   ```

### Phase 4: Final Verification (10 min)
1. ⬜ Run full test suite: `pytest tests/ -v`
2. ⬜ Verify `data/projects/` is clean after tests
3. ⬜ Run integration tests: `pytest -m integration -v`
4. ⬜ Commit fixture changes

---

## Edge Cases to Handle

### 1. **Integration Tests Already Use tmp_path**
- `test_vector_store_integration.py` already uses `tempfile.mkdtemp()`
- Should migrate to `tmp_path` for consistency
- Minimal changes needed (fixture already isolates)

### 2. **Tests with Explicit Paths**
Some tests might use absolute paths:
```python
store = VectorStore(
    project_name="test",
    persist_directory="/some/absolute/path"
)
```
These should **not** be redirected. Solution: Only redirect if path contains "data/projects".

### 3. **Windows Path Separators**
Need to handle both:
- Unix: `data/projects`
- Windows: `data\\projects`

Already covered in fixture with:
```python
if "data/projects" in path_str or "data\\projects" in path_str:
```

### 4. **Nested Path Objects**
Some code does: `Path("data") / "projects" / project_name`

The fixture only intercepts `Path()` constructor, so this should still work since the constructor is called with "data" first.

**Potential issue:** Need to verify this pattern is caught.

**Solution if not:** Also patch `Path.__truediv__()` to check results.

---

## Risk Assessment

### Low Risk ✅
- Automatic cleanup prevents pollution
- tmp_path is pytest built-in (well-tested)
- Fixture isolation is pytest best practice

### Medium Risk ⚠️
- Path redirection might have edge cases
- Some tests might rely on specific paths
- Debugging path issues could be tricky

### Mitigation Strategies
1. **Incremental testing**: Run small batches of tests first
2. **Fallback**: Cleanup fixture catches leaks even if redirection fails
3. **Verbose logging**: Add debug prints to fixture during development
4. **Easy rollback**: Single commit, easy to revert if issues

---

## Success Criteria

After implementation, verify:

1. ✅ All 479+ unit tests pass
2. ✅ `data/projects/` directory contains ONLY real projects
3. ✅ No test artifact folders (naruto_wiki, etc.)
4. ✅ Tests can run multiple times without pollution
5. ✅ Integration tests still pass
6. ✅ Fixture works on both Unix and Windows paths

---

## Alternative: Simpler Cleanup-Only Approach

If path redirection proves too complex, fall back to **cleanup-only**:

```python
@pytest.fixture(autouse=True, scope="function")
def cleanup_test_projects():
    """Clean up test project directories after each test."""
    yield
    import shutil
    from pathlib import Path

    test_projects = ["naruto_wiki", "avatar_wiki", "test_wiki", "test_project", "bleach_wiki"]
    for proj in test_projects:
        proj_path = Path("data/projects") / proj
        if proj_path.exists():
            shutil.rmtree(proj_path, ignore_errors=True)
```

**Pros:**
- ✅ Very simple (5 lines)
- ✅ Zero risk of breaking tests
- ✅ Solves pollution problem

**Cons:**
- ❌ Tests still create real directories (just cleaned up after)
- ❌ Not true isolation (tests could interfere)
- ❌ Doesn't follow pytest best practices

**Use this if:** Path redirection causes unexpected issues.

---

## Next Steps

Ready to proceed? Choose approach:
1. **Recommended:** Implement hybrid approach (redirection + cleanup)
2. **Conservative:** Start with cleanup-only, upgrade later
3. **Thorough:** Explicit tmp_path in all tests (highest quality, most work)

What's your preference?
