try:
    from . import agent
except ImportError:
    # Allows utilities (data, outreach, config) to be imported and tested without google-adk
    agent = None
