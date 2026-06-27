# Notebooks

Runnable Jupyter notebooks that demonstrate every subsystem end to end. They use the
bundled [example organizations](../examples/organizations/) and a throwaway database, so
they run deterministically with no external services, API keys, or LLMs.

| Notebook | Topic |
|---|---|
| [`01_import.ipynb`](01_import.ipynb) | Import transcripts and inspect stored memory |
| [`02_search.ipynb`](02_search.ipynb) | Ranked retrieval and result inspection |
| [`03_graph.ipynb`](03_graph.ipynb) | Organizational graph: summary, neighbors, paths |
| [`04_intelligence.ipynb`](04_intelligence.ipynb) | Insights, metrics, recommendations, reports |
| [`05_sdk.ipynb`](05_sdk.ipynb) | The Python SDK in local and HTTP modes |
| [`06_api.ipynb`](06_api.ipynb) | The REST API (in-process and live server) |
| [`07_deployment.ipynb`](07_deployment.ipynb) | Backup/restore, metrics, and deployment |

## Running

```bash
pip install -e ".[api,sdk]" jupyter
jupyter lab notebooks/
```

Run cells top to bottom. Each notebook is independent and creates its own temporary
database. You can also execute them headlessly:

```bash
jupyter nbconvert --to notebook --execute notebooks/01_import.ipynb --stdout >/dev/null
```
