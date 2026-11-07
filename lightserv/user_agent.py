"""Browser fields for the existing non-null audit log columns."""
from ua_parser import user_agent_parser


def browser_details(value):
    parsed = user_agent_parser.Parse(value or "")
    browser = parsed["user_agent"]
    return (browser.get("family", "unknown").lower(),
            ".".join(browser[key] for key in ("major", "minor", "patch") if browser.get(key)) or "unknown",
            parsed["os"].get("family", "unknown").lower())
