import sys
import os

# Ensure the root of the project and app folder are on PYTHONPATH to resolve imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

from app.agents.coordinator import coordinator_adk_agent

root_agent = coordinator_adk_agent
