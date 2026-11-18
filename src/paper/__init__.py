"""A daily news issue for Claude to write: the engine finds and ranks, Claude chooses."""

import warnings

# urllib3 (under trafilatura) warns on import that SOCKS proxies need an extra; nobody here uses one.
warnings.filterwarnings("ignore", message="SOCKS support in urllib3")
