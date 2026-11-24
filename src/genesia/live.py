import base64
from importlib.resources import files
from urllib.parse import urljoin, urlsplit

from .environments import authorize
from .runtime import EvidenceStore
from .schemas import EnvironmentSpec, ExecutionResult, Observation, Target


def model_visible_text(text: str) -> str:
    def is_private_use(character: str) -> bool:
        value = ord(character)
        return 0xE000 <= value <= 0xF8FF or 0xF0000 <= value <= 0xFFFFD or 0x100000 <= value <= 0x10FFFD

    return "\n".join(
        normalized
        for line in text.splitlines()
        if (
            normalized := " ".join(
                "".join(character for character in line if not is_private_use(character)).split()
            )
        )
    )


def origin(url):
    parsed = urlsplit(url)
    return parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)


class LiveEnvironment:
    def __init__(self, spec: EnvironmentSpec, store: EvidenceStore, owner: dict):
        from playwright.sync_api import sync_playwright

        self.store, self.owner, self.sequence = store, owner, 0
        self.spec = spec
        self.latest = None
        self.screenshot_width = spec.screenshot_width
        self.screenshot_quality = spec.screenshot_quality
        self.handoff_urls = list(spec.handoff_urls)
        self.handoff_index = 0
        self.allowed_origin = origin(spec.start_url)
        self.playwright = sync_playwright().start()
        self.browser = None
        try:
            self.browser = self.playwright.chromium.launch(headless=spec.headless)
            self._open_stage(spec.start_url)
        except Exception:
            self.close()
            raise

    def _open_stage(self, url):
        self.context = self.browser.new_context(
            viewport={"width": self.spec.width, "height": self.spec.height},
            accept_downloads=False,
            service_workers="block",
        )
        self.context.route(
            "**/*",
            lambda route: (
                route.continue_() if origin(route.request.url) == self.allowed_origin else route.abort()
            ),
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(7000)
        self.page.on("dialog", lambda dialog: dialog.dismiss())
        self.context.on("page", lambda page: page.close() if page != self.page else None)
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.evaluate("() => document.fonts.ready")

    @property
    def can_advance(self):
        return self.handoff_index < len(self.handoff_urls)

    @property
    def can_go_back(self):
        previous_url = self._previous_history_url()
        return bool(previous_url and origin(previous_url) == self.allowed_origin)

    def _previous_history_url(self):
        session = self.context.new_cdp_session(self.page)
        try:
            history = session.send("Page.getNavigationHistory")
            index = history["currentIndex"]
            return history["entries"][index - 1]["url"] if index > 0 else None
        finally:
            session.detach()

    def _screenshot(self):
        if not self.screenshot_width or self.screenshot_width == self.page.viewport_size["width"]:
            return self.page.screenshot(type="jpeg", quality=self.screenshot_quality, animations="disabled")
        viewport = self.page.viewport_size
        scale = self.screenshot_width / viewport["width"]
        session = self.context.new_cdp_session(self.page)
        try:
            result = session.send(
                "Page.captureScreenshot",
                {
                    "format": "jpeg",
                    "quality": self.screenshot_quality,
                    "fromSurface": True,
                    "captureBeyondViewport": False,
                    "clip": {
                        "x": 0,
                        "y": 0,
                        "width": viewport["width"],
                        "height": viewport["height"],
                        "scale": scale,
                    },
                },
            )
            return base64.b64decode(result["data"])
        finally:
            session.detach()

    def observe(self):
        self.sequence += 1
        targets = self.page.evaluate(files("genesia").joinpath("resources/observe.js").read_text("utf-8"))
        visible = self.page.evaluate(
            r"""() => {
                const text = [];
                const clippedByAncestor = (element, rect) => {
                    for (let parent = element.parentElement; parent && parent !== document.body;
                        parent = parent.parentElement) {
                        const style = getComputedStyle(parent);
                        const clipsX = ['auto', 'scroll', 'hidden', 'clip'].includes(style.overflowX);
                        const clipsY = ['auto', 'scroll', 'hidden', 'clip'].includes(style.overflowY);
                        if (!clipsX && !clipsY) continue;
                        const bounds = parent.getBoundingClientRect();
                        if ((clipsX && (rect.right <= bounds.left || rect.left >= bounds.right)) ||
                            (clipsY && (rect.bottom <= bounds.top || rect.top >= bounds.bottom))) return true;
                    }
                    return false;
                };
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                while (walker.nextNode()) {
                    const node = walker.currentNode;
                    const value = (node.textContent || '').trim().replace(/\s+/g, ' ');
                    if (!value || !node.parentElement) continue;
                    if (node.parentElement.closest('[data-genesia-mark]')) continue;
                    const style = getComputedStyle(node.parentElement);
                    if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0)
                        continue;
                    const range = document.createRange();
                    range.selectNodeContents(node);
                    const shown = [...range.getClientRects()].some(rect =>
                        rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < innerHeight &&
                        rect.right > 0 && rect.left < innerWidth &&
                        !clippedByAncestor(node.parentElement, rect));
                    if (shown) text.push(value);
                }
                const scrollables = [...document.querySelectorAll('*')].filter(element => {
                    const rect = element.getBoundingClientRect();
                    const style = getComputedStyle(element);
                    return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < innerHeight &&
                        element.scrollHeight > element.clientHeight + 2 &&
                        ['auto', 'scroll'].includes(style.overflowY);
                });
                const target = scrollables.sort((left, right) =>
                    right.clientWidth * right.clientHeight - left.clientWidth * left.clientHeight)[0] ||
                    document.scrollingElement;
                const top = Math.round(target?.scrollTop || 0);
                const max = Math.max(0, Math.round((target?.scrollHeight || 0) - (target?.clientHeight || 0)));
                return {
                    text: [...new Set(text)].join('\n').slice(0, 10000),
                    scroll: {top, max, can_scroll_up: top > 0, can_scroll_down: top < max},
                };
            }"""
        )
        self.page.evaluate(
            "() => document.querySelectorAll('[data-genesia-mark]').forEach(node => node.remove())"
        )
        viewport = self.page.viewport_size
        coordinate_scale = (self.screenshot_width or viewport["width"]) / viewport["width"]
        if coordinate_scale != 1:
            for target in targets:
                if target.get("x") is not None:
                    target["x"] *= coordinate_scale
                if target.get("y") is not None:
                    target["y"] *= coordinate_scale
        for target in targets:
            target["name"] = model_visible_text(target["name"]).replace("\n", " ") or "Unlabeled control"
            target["description"] = model_visible_text(target.get("description", "")).replace("\n", " ")
        image = self.store.put(self._screenshot(), "frame", ".jpg", **self.owner)
        observation = Observation(
            id=f"o{self.sequence}",
            mode="live",
            url=self.page.url,
            text=model_visible_text(visible["text"]),
            scroll=visible["scroll"],
            image_refs=[image],
            targets=[Target.model_validate(target) for target in targets],
        )
        observation.evidence_refs = [image, self.store.json(observation, "observation", **self.owner)]
        self.latest = observation
        return observation

    def _resolve_target(self, target: Target):
        selector = f'[data-genesia-target="{target.id}"]'
        locator = self.page.locator(selector)
        count = locator.count()
        if count == 1:
            return locator, False
        if count > 1:
            raise ValueError("Observed target label is no longer unique")
        if not target.fingerprint:
            raise ValueError("Observed target was replaced and has no stable fingerprint")
        rebound = self.page.evaluate(
            r"""({targetId, fingerprint}) => {
                const normalize = value => (value || '').trim().replace(/\s+/g, ' ').slice(0, 160);
                const matches = [...document.querySelectorAll(fingerprint.tag)].filter(element =>
                    Object.entries(fingerprint).every(([key, expected]) => {
                        const actual = key === 'tag' ? element.tagName.toLowerCase() :
                            key === 'text' ? normalize(element.innerText) : element.getAttribute(key);
                        return actual === expected;
                    }));
                if (matches.length === 1) matches[0].setAttribute('data-genesia-target', targetId);
                return matches.length;
            }""",
            {
                "targetId": target.id,
                "fingerprint": target.fingerprint,
            },
        )
        if rebound != 1:
            raise ValueError(
                "Observed target was replaced and could not be uniquely rebound"
                if rebound == 0
                else "Observed target was replaced and its fingerprint matched multiple elements"
            )
        return self.page.locator(selector), True

    def act(self, action):
        if self.latest is None:
            raise ValueError("Observe before each browser action; stale targets cannot be reused")
        authorize(
            action,
            self.latest,
            {"click", "right_click", "type", "select", "press", "back", "scroll", "advance", "wait"},
        )
        if action.action == "press" and action.value not in {
            "Enter",
            "Escape",
            "Tab",
            "Shift+Tab",
            "ArrowDown",
            "ArrowUp",
            "ArrowLeft",
            "ArrowRight",
            "Space",
        }:
            raise ValueError("Keyboard shortcut is outside the permitted key set")
        observed_target = (
            next(target for target in self.latest.targets if target.id == action.target_id)
            if action.target_id
            else None
        )
        self.latest = None
        try:
            target, rebound = self._resolve_target(observed_target) if observed_target else (None, False)
            if target and action.action in {"click", "right_click"}:
                href = target.get_attribute("href")
                if href and origin(urljoin(self.page.url, href)) != self.allowed_origin:
                    return ExecutionResult(success=False, message="External link blocked before navigation")
            if action.action in {"click", "right_click"}:
                target.click(button="right" if action.action == "right_click" else "left")
            elif action.action == "type":
                target.fill(action.value)
            elif action.action == "select":
                target.select_option(label=action.value)
            elif action.action == "press":
                self.page.keyboard.press(action.value)
            elif action.action == "back":
                if not self.can_go_back:
                    return ExecutionResult(
                        success=False,
                        message=(
                            "Browser back outside the permitted origin was blocked before navigation; "
                            "current page preserved"
                        ),
                    )
                self.page.go_back(wait_until="domcontentloaded")
            elif action.action == "scroll":
                result = self.page.evaluate(
                    r"""direction => {
                        const visible = element => {
                            const rect = element.getBoundingClientRect();
                            const style = getComputedStyle(element);
                            return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < innerHeight &&
                                style.visibility !== 'hidden' && style.display !== 'none';
                        };
                        const candidates = [...document.querySelectorAll('*')].filter(element => {
                            const style = getComputedStyle(element);
                            return visible(element) && element.scrollHeight > element.clientHeight + 2 &&
                                ['auto', 'scroll'].includes(style.overflowY);
                        });
                        const target = candidates.sort((left, right) =>
                            right.clientWidth * right.clientHeight - left.clientWidth * left.clientHeight)[0] ||
                            document.scrollingElement;
                        const before = target.scrollTop;
                        const amount = Math.max(120, Math.round(target.clientHeight * 0.8));
                        target.scrollBy({top: direction === 'down' ? amount : -amount, behavior: 'instant'});
                        return {before, after: target.scrollTop, max: target.scrollHeight - target.clientHeight};
                    }""",
                    action.value,
                )
                if result["after"] == result["before"]:
                    return ExecutionResult(success=False, message=f"Cannot scroll {action.value} any further")
            elif action.action == "advance":
                if not self.can_advance:
                    return ExecutionResult(success=False, message="No later live stage is available")
                next_url = self.handoff_urls[self.handoff_index]
                self.context.close()
                self._open_stage(next_url)
                self.handoff_index += 1
            elif action.action == "wait":
                self.page.wait_for_timeout(500)
            self.page.evaluate(
                "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
            )
            if origin(self.page.url) != self.allowed_origin:
                return ExecutionResult(success=False, message="Navigation outside permitted origin blocked")
            return ExecutionResult(
                success=True,
                message=f"{action.action} executed"
                + (" after uniquely rebinding replaced target" if rebound else "")
                + "; inspect next observation",
            )
        except Exception as error:
            return ExecutionResult(
                success=False,
                message=f"Browser action failed before confirmed execution: {type(error).__name__}: "
                f"{str(error)[:300]}; not retried",
            )

    def close(self):
        try:
            if self.browser:
                self.browser.close()
        finally:
            self.playwright.stop()
