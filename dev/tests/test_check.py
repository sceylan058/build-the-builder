"""One failing fixture per check.py rule.   python3 -m unittest dev/tests/test_check.py -v"""
import copy, json, pathlib, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "builder"))
import check  # noqa: E402

WF = json.load(open(ROOT / "dev/out/brief-b.workflow.json"))
CFG = json.load(open(ROOT / "dev/out/brief-b.config.json"))
API = json.load(open(ROOT / "tools/openapi.json"))
BUNDLE = (ROOT / "briefs/brief-a.md").read_text() + (ROOT / "briefs/brief-b.md").read_text()


def run(wf=None, cfg=None, api=None, bundle=None, quick=True):
    return check.run_checks(wf or WF, api or API, cfg or CFG, BUNDLE if bundle is None else bundle, quick=quick)


def tool(wf, node, name):
    return [t for t in wf["nodes"][node]["tools"] if t["function"]["name"] == name][0]


class Base(unittest.TestCase):
    def assertFlags(self, errors, needle):
        self.assertTrue(any(needle in e for e in errors), f"expected an error containing {needle!r}, got: {errors[:6]}")


class TestBaseline(Base):
    def test_baseline_passes(self):
        self.assertEqual(run(quick=False), [])


class TestR1OpenAPI(Base):
    def test_wrong_host(self):
        wf = copy.deepcopy(WF)
        tool(wf, "record", "create_promise")["function"]["parameters"]["properties"]["url"]["default"] = "https://elsewhere.example/v1/create_promise"
        self.assertFlags(run(wf), "R1 openapi: node record tool create_promise calls")

    def test_unknown_path(self):
        api = copy.deepcopy(API)
        api["paths"].pop("/add_note")
        self.assertFlags(run(api=api), "which is not in the tool API file")

    def test_unknown_body_field(self):
        wf = copy.deepcopy(WF)
        tool(wf, "record", "create_promise")["function"]["parameters"]["properties"]["body"]["properties"]["promise_date"] = {"type": "string", "default": "{{promise_date}}"}
        self.assertFlags(run(wf), "sends body field 'promise_date'")

    def test_missing_required(self):
        wf = copy.deepcopy(WF)
        tool(wf, "record", "create_promise")["function"]["parameters"]["properties"]["body"]["properties"].pop("date")
        self.assertFlags(run(wf), "never sends required field 'date'")

    def test_baked_literal_not_in_enum(self):
        wf = copy.deepcopy(WF)
        b = wf["nodes"]["close"]["pre_actions"][0]["function"]["parameters"]["properties"]["body"]["properties"]
        b["outcome"]["default"] = "no_contact"
        self.assertFlags(run(wf), "bakes outcome='no_contact'")

    def test_offered_enum_not_allowed(self):
        wf = copy.deepcopy(WF)
        tool(wf, "negotiate", "transfer_to_agent")["function"]["parameters"]["properties"]["body"]["properties"]["queue"]["enum"].append("vip")
        self.assertFlags(run(wf), "offers queue values ['vip']")

    def test_config_outcome_not_in_enum(self):
        cfg = copy.deepcopy(CFG)
        cfg["outcomes"]["by_hint"]["unclear"] = ["no_contact", "unclear"]
        self.assertFlags(run(cfg=cfg), "outcomes ['no_contact'] are not allowed")

    def test_identity_field_not_in_enum(self):
        cfg = copy.deepcopy(CFG)
        cfg["flow"]["nodes"]["identity"]["verify"]["questions"][0]["field"] = "postcode"
        self.assertFlags(run(cfg=cfg), "identity questions ['postcode']")

    def test_item_type_not_in_enum(self):
        cfg = copy.deepcopy(CFG)
        cfg["items"]["label"]["templates"]["mortgage"] = "mortgage"
        self.assertFlags(run(cfg=cfg), "items.label.templates keys ['mortgage']")


class TestR2Graph(Base):
    def test_missing_target(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["opening"]["transitions"][0]["target_node"] = "nowhere"
        self.assertFlags(run(wf), "routes to missing node 'nowhere'")

    def test_unreachable(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["orphan"] = copy.deepcopy(wf["nodes"]["farewell"])
        self.assertFlags(run(wf), "node orphan is not reachable")

    def test_dead_end(self):
        wf = copy.deepcopy(WF)
        n = wf["nodes"]["third_party"]
        n["transitions"] = [{"target_node": "third_party", "description": "stay", "condition": {"operator": "always"}}]
        n["max_turn_transition"] = "third_party"
        self.assertFlags(run(wf), "node third_party has no path to an end_call node")

    def test_passthrough_without_always(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["setup"]["transitions"].pop()
        self.assertFlags(run(wf), "passthrough node setup does not end with an always transition")

    def test_turns_without_transition(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["negotiate"].pop("max_turn_transition")
        self.assertFlags(run(wf), "node negotiate sets max_node_turns without max_turn_transition")

    def test_tools_on_code_node(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["setup"]["tools"] = [copy.deepcopy(tool(wf, "record", "create_promise"))]
        self.assertFlags(run(wf), "node setup (code) has tools")

    def test_pre_actions_on_conversation(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["negotiate"]["pre_actions"] = copy.deepcopy(wf["nodes"]["fetch_account"]["pre_actions"])
        self.assertFlags(run(wf), "node negotiate (conversation) has pre_actions")

    def test_mapping_path(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["fetch_account"]["response_mapping"][0]["path"] = "products"
        self.assertFlags(run(wf), "paths must start with 'data.'")

    def test_null_value(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["opening"]["routing_prompt"] = None
        self.assertFlags(run(wf), "null value at .nodes.opening.routing_prompt")

    def test_braces_in_code(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["farewell"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] += "x = '{{y}}'\n"
        self.assertFlags(run(wf), "code in farewell contains")

    def test_unproduced_placeholder(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["negotiate"]["task_message"] += "\n{{loyalty_tier}}"
        self.assertFlags(run(wf), "node negotiate uses {{loyalty_tier}} but nothing produces it")

    def test_extraction_without_confidence(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["opening"]["extraction_schema"][0].pop("min_confidence")
        self.assertFlags(run(wf), "has no min_confidence")


class TestR3Code(Base):
    def test_code_error_marker(self):
        wf = copy.deepcopy(WF)
        c = wf["nodes"]["compute_facts"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        c["default"] = c["default"].replace("    rows = [p for p in find_items()", "    1 / 0\n    rows = [p for p in find_items()")
        self.assertFlags(run(wf), "R3 code:")

    def test_wrong_today(self):
        wf = copy.deepcopy(WF)
        c = wf["nodes"]["setup"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]
        c["default"] = c["default"].replace("    vars['today_iso'] = d_iso(today)", "    vars['today_iso'] = '2026-01-01'")
        self.assertFlags(run(wf), "today_iso=2026-01-01 but now=")

    def test_snippet_that_raises(self):
        wf = copy.deepcopy(WF)
        wf["nodes"]["farewell"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"] = "raise ValueError('boom')\n"
        self.assertFlags(run(wf), "node farewell raised ValueError")


class TestR4Provenance(Base):
    def test_changed_holiday(self):
        cfg = copy.deepcopy(CFG)
        cfg["calendar"]["holidays"][1] = "2026-11-12"
        self.assertFlags(run(cfg=cfg), "calendar.holidays has 2026-11-12")

    def test_changed_deadline(self):
        cfg = copy.deepcopy(CFG)
        cfg["items"]["tiers"]["list"][0]["limit"]["n"] = 13
        self.assertFlags(run(cfg=cfg), "items.tiers.list[0].limit.n = 13")

    def test_changed_window(self):
        cfg = copy.deepcopy(CFG)
        cfg["clock"]["windows"][0]["end"] = "18:30"
        self.assertFlags(run(cfg=cfg), "clock.windows[0].end = 18:30")

    def test_invented_quote(self):
        cfg = copy.deepcopy(CFG)
        cfg["flow"]["nodes"]["negotiate"]["task"] += ' Always say "we can waive the late fee today".'
        self.assertFlags(run(cfg=cfg), 'quoted text "we can waive the late fee today"')

    def test_derived_note_allows_value(self):
        cfg = copy.deepcopy(CFG)
        cfg["items"]["tiers"]["list"][0]["limit"]["n"] = 13
        cfg["provenance"] = {"derived": {"items.tiers.list[0].limit.n=13": "12th business day counted from tomorrow"}}
        self.assertFalse([e for e in run(cfg=cfg) if "R4" in e])


class TestR5Spoken(Base):
    def test_forbidden_word_in_opening(self):
        cfg = copy.deepcopy(CFG)
        cfg["flow"]["nodes"]["opening"]["enter"]["tts"] = "Hello, this is Freya Bank calling about your debt."
        self.assertFlags(run(cfg=cfg), "R5 spoken: node opening first line says 'debt'")

    def test_forbidden_word_in_pre_verification_closing(self):
        cfg = copy.deepcopy(CFG)
        cfg["closing"]["lines"]["wrong_number"] = "Sorry, we will chase this payment elsewhere. Goodbye."
        self.assertFlags(run(cfg=cfg), "R5 spoken: closing line for end:wrong_number says 'payment'")


if __name__ == "__main__":
    unittest.main()
