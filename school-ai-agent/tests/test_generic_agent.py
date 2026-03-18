import unittest
from unittest.mock import AsyncMock, Mock, patch

from graph.agents.conversation_agent import ConversationAgent
from graph.agents.generic_mcp_agent import GenericMCPAgent
from graph.core.decision_parsing import DecisionParser
from graph.core.mcp_client import MCPClient
from graph.core.schema_discovery import SchemaDiscovery


def build_tool(
    name,
    *,
    description=None,
    params=None,
    query=None,
    body=None,
    params_required=None,
    query_required=None,
    body_required=None,
):
    discovery = SchemaDiscovery(Mock())
    input_schema = {"properties": {}}

    if params is not None:
        input_schema["properties"]["params"] = {
            "type": "object",
            "properties": params,
            "required": params_required or [],
        }
    if query is not None:
        input_schema["properties"]["query"] = {
            "type": "object",
            "properties": query,
            "required": query_required or [],
        }
    if body is not None:
        input_schema["properties"]["body"] = {
            "type": "object",
            "properties": body,
            "required": body_required or [],
        }

    tool = {
        "name": name,
        "description": description or name,
        "inputSchema": input_schema,
    }
    return discovery._format_tools_for_llm([tool])[0]


class GenericMCPAgentTests(unittest.IsolatedAsyncioTestCase):
    def make_agent(self):
        agent = GenericMCPAgent.__new__(GenericMCPAgent)
        agent.mcp_client = Mock()
        agent.schema_discovery = None
        agent.llm = Mock()
        agent.parser = DecisionParser()
        agent.max_retries = 2
        return agent

    async def test_create_class_arguments_map_to_body_fields(self):
        agent = self.make_agent()
        tool = build_tool(
            "createClass",
            body={
                "class_id": {"type": "string"},
                "class_name": {"type": "string"},
            },
            body_required=["class_id", "class_name"],
        )

        normalized, clarification = await agent._resolve_arguments(
            user_request="Create a class with class_id c301 and class_name Class 301",
            tool_meta=tool,
            proposed_args={"class_id": "c301", "class_name": "Class 301"},
        )

        self.assertIsNone(clarification)
        self.assertEqual(
            normalized,
            {
                "params": {},
                "query": {},
                "body": {"class_id": "c301", "class_name": "Class 301"},
            },
        )

    async def test_get_marks_by_student_maps_student_id_to_path_param(self):
        agent = self.make_agent()
        tool = build_tool(
            "getMarksByStudent",
            description="GET /api/marks/by-student/{studentId}",
            params={"studentId": {"type": "string"}},
            params_required=["studentId"],
        )

        normalized, clarification = await agent._resolve_arguments(
            user_request="Show all marks for student s3",
            tool_meta=tool,
            proposed_args={"student_id": "s3"},
        )

        self.assertIsNone(clarification)
        self.assertEqual(normalized["params"], {"studentId": "s3"})

    async def test_get_by_id_prefers_specific_tool_and_extracts_exact_id(self):
        agent = self.make_agent()
        tools = [
            build_tool("getClasses", description="GET /api/classes"),
            build_tool(
                "getClassById",
                description="GET /api/classes/{id}",
                params={"id": {"type": "string", "pattern": "^c[0-9]+$"}},
                params_required=["id"],
            ),
        ]

        selected = agent._select_tool_name("give details of class c301", tools, "getClasses")
        self.assertEqual(selected, "getClassById")

        tool = next(tool for tool in tools if tool["name"] == selected)
        normalized, clarification = await agent._resolve_arguments(
            user_request="give details of class c301",
            tool_meta=tool,
            proposed_args={},
        )

        self.assertIsNone(clarification)
        self.assertEqual(normalized["params"], {"id": "c301"})

    async def test_get_by_id_requires_full_identifier_when_request_only_has_number(self):
        agent = self.make_agent()
        tool = build_tool(
            "getClassById",
            description="GET /api/classes/{id}",
            params={"id": {"type": "string", "pattern": "^c[0-9]+$"}},
            params_required=["id"],
        )
        agent._repair_args = AsyncMock(return_value={})

        normalized, clarification = await agent._resolve_arguments(
            user_request="fetch details of class 301",
            tool_meta=tool,
            proposed_args={},
        )

        self.assertEqual(normalized["params"], {})
        self.assertIsNotNone(clarification)
        self.assertIn("params.id", clarification)

    async def test_get_by_id_does_not_coerce_existing_numeric_id(self):
        agent = self.make_agent()
        tool = build_tool(
            "getClassById",
            description="GET /api/classes/{id}",
            params={"id": {"type": "string", "pattern": "^c[0-9]+$"}},
            params_required=["id"],
        )

        normalized, clarification = await agent._resolve_arguments(
            user_request="fetch details of class 301",
            tool_meta=tool,
            proposed_args={"id": "301"},
        )

        self.assertIsNone(clarification)
        self.assertEqual(normalized["params"], {"id": "301"})

    async def test_selects_marks_record_tool_over_unrelated_subject_tool(self):
        agent = self.make_agent()
        tools = [
            build_tool(
                "getStudentsBySubject",
                description="GET /api/subjects/{id}/students",
                params={"id": {"type": "string", "pattern": "^(eng|mat|sci)[0-9]+$"}},
                params_required=["id"],
            ),
            build_tool(
                "getMarksById",
                description="GET /api/marks/{id}",
                params={"id": {"type": "string", "pattern": "^m[0-9]+$"}},
                params_required=["id"],
            ),
        ]

        selected = agent._select_tool_name("Fetch marks record m301", tools, "getStudentsBySubject")
        self.assertEqual(selected, "getMarksById")

    async def test_selects_marks_by_subject_for_subject_prompt(self):
        agent = self.make_agent()
        tools = [
            build_tool(
                "getMarksByStudent",
                description="GET /api/marks/by-student/{studentId}",
                params={"studentId": {"type": "string", "pattern": "^s[0-9]+$"}},
                params_required=["studentId"],
            ),
            build_tool(
                "getMarksBySubject",
                description="GET /api/marks/by-subject/{subjectId}",
                params={"subjectId": {"type": "string", "pattern": "^(eng|mat|sci)[0-9]+$"}},
                params_required=["subjectId"],
            ),
        ]

        selected = agent._select_tool_name("Show all marks for subject eng301", tools, None)
        self.assertEqual(selected, "getMarksBySubject")

    async def test_selects_student_and_subject_query_tool_when_both_filters_are_present(self):
        agent = self.make_agent()
        tools = [
            build_tool(
                "getMarksByStudent",
                description="GET /api/marks/by-student/{studentId}",
                params={"studentId": {"type": "string", "pattern": "^s[0-9]+$"}},
                params_required=["studentId"],
            ),
            build_tool(
                "getMarksBySubject",
                description="GET /api/marks/by-subject/{subjectId}",
                params={"subjectId": {"type": "string", "pattern": "^(eng|mat|sci)[0-9]+$"}},
                params_required=["subjectId"],
            ),
            build_tool(
                "getByStudentAndSubject",
                description="GET /api/marks",
                query={
                    "student_id": {"type": "string", "pattern": "^s[0-9]+$"},
                    "subject_id": {"type": "string", "pattern": "^(eng|mat|sci)[0-9]+$"},
                },
            ),
        ]

        selected = agent._select_tool_name("Get marks for student s301 in subject eng301", tools, None)
        self.assertEqual(selected, "getByStudentAndSubject")

    async def test_selects_delete_tool_for_delete_request(self):
        agent = self.make_agent()
        tools = [
            build_tool("getClasses", description="GET /api/classes"),
            build_tool(
                "deleteClass",
                description="DELETE /api/classes/{id}",
                params={"id": {"type": "string", "pattern": "^c[0-9]+$"}},
                params_required=["id"],
            ),
        ]

        selected = agent._select_tool_name("Delete class c301", tools, None)
        self.assertEqual(selected, "deleteClass")

    async def test_generic_alias_normalization_handles_mixed_naming(self):
        agent = self.make_agent()
        tool = build_tool(
            "createWidget",
            body={
                "widgetId": {"type": "string"},
                "display_name": {"type": "string"},
            },
            body_required=["widgetId", "display_name"],
        )

        normalized, clarification = await agent._resolve_arguments(
            user_request="create widget",
            tool_meta=tool,
            proposed_args={"widget_id": "w1", "displayName": "Widget 1"},
        )

        self.assertIsNone(clarification)
        self.assertEqual(
            normalized["body"],
            {"widgetId": "w1", "display_name": "Widget 1"},
        )

    async def test_numeric_string_is_coerced_to_number_from_schema(self):
        agent = self.make_agent()
        tool = build_tool(
            "createMarks",
            body={
                "marks_id": {"type": "string"},
                "student_id": {"type": "string"},
                "subject_id": {"type": "string"},
                "marks": {"type": "number"},
            },
            body_required=["marks_id", "student_id", "subject_id", "marks"],
        )

        normalized, clarification = await agent._resolve_arguments(
            user_request="Create marks with marks_id m301 for student s301 subject eng301 marks 78",
            tool_meta=tool,
            proposed_args={
                "marks_id": "m301",
                "student_id": "s301",
                "subject_id": "eng301",
                "marks": "78",
            },
        )

        self.assertIsNone(clarification)
        self.assertEqual(normalized["body"]["marks"], 78)

    async def test_missing_required_values_return_clarification(self):
        agent = self.make_agent()
        tool = build_tool(
            "createTeacher",
            body={
                "teacher_id": {"type": "string"},
                "name": {"type": "string"},
                "class_id": {"type": "string"},
            },
            body_required=["teacher_id", "name", "class_id"],
        )
        agent._repair_args = AsyncMock(return_value={"name": "Teacher 301"})

        normalized, clarification = await agent._resolve_arguments(
            user_request="Create a teacher named Teacher 301",
            tool_meta=tool,
            proposed_args={"name": "Teacher 301"},
        )

        self.assertEqual(normalized["body"], {"name": "Teacher 301"})
        self.assertIsNotNone(clarification)
        self.assertIn("body.teacher_id", clarification)
        self.assertIn("body.class_id", clarification)

    async def test_execute_tool_retries_on_mcp_validation_payload(self):
        agent = self.make_agent()
        tool = build_tool(
            "createThing",
            body={
                "thingId": {"type": "string"},
                "title": {"type": "string"},
            },
            body_required=["thingId", "title"],
        )
        agent.mcp_client.call_tool = AsyncMock(
            side_effect=[
                {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": "MCP error -32602: Input validation error: Invalid arguments for tool createThing",
                        }
                    ],
                },
                {"ok": True},
            ]
        )
        agent._resolve_arguments = AsyncMock(
            return_value=(
                {"params": {}, "query": {}, "body": {"thingId": "t1", "title": "Thing 1"}},
                None,
            )
        )

        result = await agent._execute_tool(
            user_request="create thing",
            tool_meta=tool,
            args={"params": {}, "query": {}, "body": {"title": "Thing 1"}},
            retry_count=0,
        )

        self.assertTrue(result["success"])
        self.assertEqual(agent.mcp_client.call_tool.await_count, 2)


class ConversationAgentTests(unittest.IsolatedAsyncioTestCase):
    def make_agent(self):
        agent = ConversationAgent.__new__(ConversationAgent)
        agent.llm = None
        return agent

    async def test_clarification_is_returned_directly(self):
        agent = self.make_agent()

        response = await agent.format_response(
            user_request="create teacher",
            execution_result={
                "success": False,
                "needs_clarification": True,
                "clarification_question": "I still need body.teacher_id. What value should I use?",
            },
        )

        self.assertEqual(response, "I still need body.teacher_id. What value should I use?")

    async def test_simple_ok_payload_uses_clean_success_message(self):
        agent = self.make_agent()

        response = await agent.format_response(
            user_request="delete record",
            execution_result={
                "success": True,
                "tool_used": "deleteThing",
                "result": {"ok": True},
            },
        )

        self.assertEqual(response, "Successfully deleted the record.")

    async def test_none_tool_used_does_not_crash(self):
        agent = self.make_agent()

        response = await agent.format_response(
            user_request="unmatched request",
            execution_result={
                "success": True,
                "tool_used": None,
                "result": "I couldn't match that request to a known tool.",
            },
        )

        self.assertEqual(response, "I couldn't match that request to a known tool.")


class MCPClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_tools_uses_configured_url(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"result": {"tools": []}}

        with patch("graph.core.mcp_client.requests.post", return_value=response) as mocked_post:
            client = MCPClient("http://example.test/mcp")
            tools = await client.list_tools()

        self.assertEqual(tools, [])
        self.assertEqual(mocked_post.call_args.args[0], "http://example.test/mcp")


if __name__ == "__main__":
    unittest.main()
