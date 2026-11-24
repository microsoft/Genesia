import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from PIL import Image
from test_workflow import ScriptedModel, task_fixture

from genesia.api import run
from genesia.live import LiveEnvironment
from genesia.runtime import EvidenceStore
from genesia.schemas import Action, EnvironmentSpec

pytestmark = pytest.mark.browser


def test_live_observation_cleans_icon_font_target_names(tmp_path, prototype):
    store = EvidenceStore(tmp_path / "evidence")
    environment = LiveEnvironment(EnvironmentSpec(mode="live", start_url=prototype), store, {})
    try:
        environment.page.set_content(
            "<button><span>\ue70e</span><div>Colors</div><div>Accent color, transparency effects</div>"
            "</button><button>\ue765</button>"
        )
        observation = environment.observe()
        assert observation.text == "Colors\nAccent color, transparency effects"
        assert [target.name for target in observation.targets] == ["Colors", "Unlabeled control"]
        assert observation.targets[0].description == "Accent color, transparency effects"
        assert (
            observation.targets[0].fingerprint["text"] == "\ue70e Colors Accent color, transparency effects"
        )
    finally:
        environment.close()


@pytest.fixture
def prototype(tmp_path):
    page = tmp_path / "index.html"
    page.write_text(
        """<!doctype html><html><body style="background:#f3f8fc;color:#16324a">
<h1>Research fixture</h1><p id="state">No items</p>
<button onclick="document.getElementById('state').textContent='Item created'">Create item</button>
<button disabled>Disabled</button><a href="http://127.0.0.1:1/forbidden">External</a>
</body></html>""",
        encoding="utf-8",
    )
    (tmp_path / "next.html").write_text("<!doctype html><h1>Version B</h1>", encoding="utf-8")
    (tmp_path / "spa.html").write_text(
        """<!doctype html><h1 id="title">Overview</h1><button id="open">Open detail</button>
<script>
let parentRoute = null;
const render = () => {
    const detail = location.hash === '#detail';
    document.getElementById('title').textContent = detail ? 'Detail' : 'Overview';
    document.getElementById('open').hidden = detail;
    let back = document.getElementById('back');
    if (detail && !back) {
        back = document.createElement('button');
        back.id = 'back';
        back.textContent = 'Back';
        back.onclick = () => {
            if (!parentRoute) return;
            history.pushState({}, '', parentRoute);
            render();
        };
        document.body.appendChild(back);
    } else if (!detail && back) back.remove();
};
document.getElementById('open').onclick = () => {
    parentRoute = '#overview';
    history.replaceState({}, '', '#detail');
    render();
};
render();
</script>""",
        encoding="utf-8",
    )
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/index.html"
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_real_browser_screenshot_and_action(tmp_path, prototype):
    store = EvidenceStore(tmp_path / "evidence")
    environment = LiveEnvironment(EnvironmentSpec(mode="live", start_url=prototype), store, {})
    try:
        before = environment.observe()
        target = next(target for target in before.targets if target.name == "Create item")
        assert target.fingerprint["tag"] == "button"
        assert target.fingerprint["text"] == "Create item"
        assert target.actions == ["click", "right_click"]
        assert target.x is not None and 0 < target.x < 1280
        assert target.y is not None and 0 < target.y < 720
        with pytest.raises(ValueError, match="incompatible"):
            environment.act(
                Action(action="select", target_id=target.id, value="Invalid", intent="Wrong action")
            )
        assert environment.act(Action(action="click", target_id=target.id, intent="Create")).success
        with pytest.raises(ValueError, match="stale"):
            environment.act(Action(action="click", target_id=target.id, intent="Repeat"))
        after = environment.observe()
        assert "Item created" in after.text
        assert store.refs[before.image_refs[0]].sha256 != store.refs[after.image_refs[0]].sha256
        assert len(store.path(after.image_refs[0]).read_bytes()) > 1000
        target = next(target for target in after.targets if target.disabled)
        with pytest.raises(ValueError):
            environment.act(Action(action="click", target_id=target.id, intent="Invalid"))
        with pytest.raises(ValueError):
            environment.act(Action(action="press", value="Control+L", intent="Address"))
        external = next(target for target in after.targets if target.name == "External")
        external_selector = f'[data-genesia-target="{external.id}"]'
        environment.page.locator(external_selector).evaluate(
            "element => { const copy = element.cloneNode(true); copy.removeAttribute('data-genesia-target'); element.replaceWith(copy); }"
        )
        blocked = environment.act(Action(action="click", target_id=external.id, intent="External"))
        assert not blocked.success
        assert blocked.message == "External link blocked before navigation"
        assert environment.page.url == prototype
    finally:
        environment.close()


def test_browser_back_cannot_strand_live_session_outside_origin(tmp_path, prototype):
    store = EvidenceStore(tmp_path / "evidence")
    environment = LiveEnvironment(EnvironmentSpec(mode="live", start_url=prototype), store, {})
    try:
        observation = environment.observe()
        assert not environment.can_go_back
        result = environment.act(Action(action="back", intent="Return"))
        assert not result.success
        assert "blocked before navigation" in result.message
        assert "current page preserved" in result.message
        assert environment.page.url == prototype
        observation = environment.observe()
        target = next(target for target in observation.targets if target.name == "Create item")
        assert environment.act(Action(action="click", target_id=target.id, intent="Continue")).success
    finally:
        environment.close()


def test_blocked_browser_back_preserves_spa_state_and_in_app_back(tmp_path, prototype):
    spa = prototype.replace("index.html", "spa.html#overview")
    store = EvidenceStore(tmp_path / "evidence")
    environment = LiveEnvironment(EnvironmentSpec(mode="live", start_url=spa), store, {})
    try:
        observation = environment.observe()
        open_detail = next(target for target in observation.targets if target.name == "Open detail")
        assert environment.act(Action(action="click", target_id=open_detail.id, intent="Open")).success
        assert environment.page.url.endswith("#detail")
        assert not environment.can_go_back

        environment.observe()
        blocked = environment.act(Action(action="back", intent="Return"))
        assert not blocked.success
        assert environment.page.url.endswith("#detail")

        observation = environment.observe()
        in_app_back = next(target for target in observation.targets if target.name == "Back")
        assert environment.act(Action(action="click", target_id=in_app_back.id, intent="Return")).success
        assert environment.page.url.endswith("#overview")
    finally:
        environment.close()


def test_browser_back_allows_previous_page_on_same_origin(tmp_path, prototype):
    store = EvidenceStore(tmp_path / "evidence")
    environment = LiveEnvironment(EnvironmentSpec(mode="live", start_url=prototype), store, {})
    try:
        next_url = prototype.replace("index.html", "next.html")
        environment.page.goto(next_url, wait_until="domcontentloaded")
        assert environment.can_go_back
        environment.observe()
        result = environment.act(Action(action="back", intent="Return"))
        assert result.success
        assert environment.page.url == prototype
    finally:
        environment.close()


def test_live_screenshot_preserves_viewport_layout_at_lower_resolution(tmp_path, prototype):
    store = EvidenceStore(tmp_path / "evidence")
    environment = LiveEnvironment(
        EnvironmentSpec(
            mode="live",
            start_url=prototype,
            width=1200,
            height=768,
            screenshot_width=1000,
            screenshot_quality=70,
        ),
        store,
        {},
    )
    try:
        button_bounds = environment.page.get_by_role("button", name="Create item").bounding_box()
        observation = environment.observe()
        assert environment.page.viewport_size == {"width": 1200, "height": 768}
        with Image.open(store.path(observation.image_refs[0])) as image:
            assert image.size == (1000, 640)
        target = next(target for target in observation.targets if target.name == "Create item")
        assert target.x == pytest.approx((button_bounds["x"] + button_bounds["width"] / 2) * 1000 / 1200)
        assert target.y == pytest.approx((button_bounds["y"] + button_bounds["height"] / 2) * 1000 / 1200)
        assert environment.page.locator("[data-genesia-mark]").count() == 0
        assert "pp-" not in observation.text
    finally:
        environment.close()


def test_live_scroll_reveals_controls_below_the_viewport(tmp_path, prototype):
    store = EvidenceStore(tmp_path / "evidence")
    environment = LiveEnvironment(EnvironmentSpec(mode="live", start_url=prototype), store, {})
    try:
        environment.page.set_content(
            """<!doctype html><main style="height:400px;overflow-y:auto">
    <button>Top</button><div style="height:500px"></div><button>Bottom</button></main>"""
        )
        before = environment.observe()
        assert {target.name for target in before.targets} == {"Top"}
        assert "Bottom" not in before.text
        assert before.scroll["can_scroll_down"]
        result = environment.act(Action(action="scroll", value="down", intent="See lower controls"))
        assert result.success
        after = environment.observe()
        assert "Bottom" in {target.name for target in after.targets}
        assert "Bottom" in after.text
        assert after.scroll["can_scroll_up"]
        assert environment.page.locator("main").evaluate("element => element.scrollTop") > 0
    finally:
        environment.close()


def test_scaled_live_observation_remains_actionable_after_scroll(tmp_path, prototype):
    store = EvidenceStore(tmp_path / "evidence")
    environment = LiveEnvironment(
        EnvironmentSpec(
            mode="live",
            start_url=prototype,
            width=1200,
            height=768,
            screenshot_width=1000,
            screenshot_quality=70,
        ),
        store,
        {},
    )
    try:
        environment.page.set_content(
            """<!doctype html><main style="height:400px;overflow-y:auto">
    <button>Top</button><div style="height:500px"></div><button>Bottom</button></main>"""
        )
        environment.observe()
        assert environment.act(Action(action="scroll", value="down", intent="See lower controls")).success
        observation = environment.observe()
        target = next(target for target in observation.targets if target.name == "Bottom")
        result = environment.act(Action(action="click", target_id=target.id, intent="Use lower control"))
        assert result.success
        assert not environment.page.is_closed()
    finally:
        environment.close()


def test_live_advance_switches_stages_without_product_ui(tmp_path, prototype):
    next_url = prototype.replace("index.html", "next.html")
    store = EvidenceStore(tmp_path / "evidence")
    environment = LiveEnvironment(
        EnvironmentSpec(
            mode="live",
            start_url=prototype,
            handoff_urls=[next_url],
            candidate_labels=["Version A", "Version B"],
        ),
        store,
        {},
    )
    try:
        environment.page.evaluate("localStorage.setItem('stage', 'A')")
        before = environment.observe()
        assert environment.can_advance
        assert "Version B" not in before.text
        assert environment.act(Action(action="advance", intent="Continue to B")).success
        after = environment.observe()
        assert not environment.can_advance
        assert after.url == next_url
        assert "Version B" in after.text
        assert "Continue to Version B" not in after.text
        assert environment.page.evaluate("localStorage.getItem('stage')") is None
    finally:
        environment.close()


def test_replaced_target_is_uniquely_rebound_before_click(tmp_path, prototype):
    store = EvidenceStore(tmp_path / "evidence")
    environment = LiveEnvironment(EnvironmentSpec(mode="live", start_url=prototype), store, {})
    try:
        observation = environment.observe()
        target = next(target for target in observation.targets if target.name == "Create item")
        environment.page.locator(f'[data-genesia-target="{target.id}"]').evaluate(
            "element => { const copy = element.cloneNode(true); copy.removeAttribute('data-genesia-target'); element.replaceWith(copy); }"
        )
        assert environment.page.locator(f'[data-genesia-target="{target.id}"]').count() == 0
        result = environment.act(Action(action="click", target_id=target.id, intent="Create"))
        assert result.success
        assert "uniquely rebinding replaced target" in result.message
        assert "Item created" in environment.page.locator("#state").inner_text()
    finally:
        environment.close()


def test_replaced_target_is_not_rebound_when_fingerprint_is_ambiguous(tmp_path, prototype):
    store = EvidenceStore(tmp_path / "evidence")
    environment = LiveEnvironment(EnvironmentSpec(mode="live", start_url=prototype), store, {})
    try:
        observation = environment.observe()
        target = next(target for target in observation.targets if target.name == "Create item")
        selector = f'[data-genesia-target="{target.id}"]'
        environment.page.locator(selector).evaluate(
            "element => { const first = element.cloneNode(true); const second = element.cloneNode(true); first.removeAttribute('data-genesia-target'); second.removeAttribute('data-genesia-target'); element.replaceWith(first, second); }"
        )
        result = environment.act(Action(action="click", target_id=target.id, intent="Create"))
        assert not result.success
        assert "matched multiple elements" in result.message
        assert "No items" in environment.page.locator("#state").inner_text()
    finally:
        environment.close()


class BrowserModel(ScriptedModel):
    def complete(self, purpose, payload, schema, **kwargs):
        if purpose == "persona_action" and not payload["history"]:
            assert "No items" in payload["observation"]["text"]
            assert "back" not in payload["allowed_actions"]
            target = next(
                target for target in payload["observation"]["targets"] if target["name"] == "Create item"
            )
            return schema.model_validate(dict(action="click", target_id=target["id"], intent="Create item"))
        if purpose == "persona_action" and payload["history"] and payload.get("prototype"):
            assert "Item created" in payload["observation"]["text"]
            self.calls.append((purpose, payload))
            return schema.model_validate(
                dict(
                    action="stop",
                    intent="The item is visibly created",
                    outcome="completed",
                    reflection=dict(
                        interest="Creating an item",
                        observed_effect="The page shows Item created",
                        judgment="The result matches the choice",
                        effect_status="visible_change",
                    ),
                )
            )
        return super().complete(purpose, payload, schema, **kwargs)


def test_three_personas_live_isolation(tmp_path, prototype):
    task = task_fixture(tmp_path)
    task.environment = EnvironmentSpec(mode="live", start_url=prototype, max_steps=3)
    task.permissions.send_screenshots = True
    model = BrowserModel()
    result = run(task, gateway=model)
    assert result.status == "completed"
    assert all(len(episode.steps) == 2 for episode in result.episodes)
    assert result.metrics["valid_responses"] == 12
    assert EvidenceStore(Path(result.output_dir)).verify()["valid"]
    assert "environment_readiness" not in [purpose for purpose, _ in model.calls]
    assert not (Path(result.output_dir) / "environment_build.json").exists()
    assert not (Path(result.output_dir) / "state_graph.json").exists()
    assert not (Path(result.output_dir) / "ui_cards.json").exists()
