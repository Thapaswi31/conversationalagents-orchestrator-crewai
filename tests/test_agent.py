import importlib
import unittest

from app.tools.analysis_tool import data_analysis_workflow
from app.tools.research_tool import research_workflow


class ConversationalAgentTests(unittest.TestCase):
    def test_conversational_agent_is_module_level_singleton_with_phase_4_tools(self):
        agent_module = importlib.import_module("app.agent")

        self.assertIs(agent_module.conversational_agent, agent_module.get_conversational_agent())
        self.assertEqual(agent_module.conversational_agent.role, "Conversational Assistant")
        self.assertTrue(agent_module.conversational_agent.memory)
        self.assertTrue(agent_module.conversational_agent.verbose)
        self.assertFalse(agent_module.conversational_agent.allow_delegation)
        self.assertIs(agent_module.conversational_agent.tools[0], research_workflow)
        self.assertIs(agent_module.conversational_agent.tools[1], data_analysis_workflow)


if __name__ == "__main__":
    unittest.main()
