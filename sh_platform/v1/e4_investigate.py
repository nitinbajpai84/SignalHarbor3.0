"""E4b: the investigation agent is now Tally (n1_tally). This module stays so that callers of the earlier names keep working."""
from sh_platform.v1.n1_tally import (AGENT, FALLBACK_NOTE, HOLES, PROMPT_VERSION, TOOL_POLICY, bridge, explain, gather, money,  # noqa: F401
                                     propose_explanation, values)
