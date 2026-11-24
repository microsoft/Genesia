() => {
    document.querySelectorAll('[data-genesia-mark]').forEach(node => node.remove());
    document.querySelectorAll('[data-genesia-target]').forEach(node => node.removeAttribute('data-genesia-target'));
    const selector = 'a[href],button,input,select,textarea,[contenteditable="true"],[role="button"],[role="link"],[role="menuitem"],[role="option"],[role="checkbox"],[role="radio"],[role="tab"],[tabindex],[data-pl="desktop"]';
    const clippedByAncestor = (element, bounds) => {
        for (let parent = element.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
            const style = getComputedStyle(parent);
            const clipsX = ['auto', 'scroll', 'hidden', 'clip'].includes(style.overflowX);
            const clipsY = ['auto', 'scroll', 'hidden', 'clip'].includes(style.overflowY);
            if (!clipsX && !clipsY) continue;
            const parentBounds = parent.getBoundingClientRect();
            if ((clipsX && (bounds.right <= parentBounds.left || bounds.left >= parentBounds.right)) ||
                (clipsY && (bounds.bottom <= parentBounds.top || bounds.top >= parentBounds.bottom))) return true;
        }
        return false;
    };
    const targets = [];
    for (const element of document.querySelectorAll(selector)) {
        const bounds = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        if (targets.length >= 100) break;
        if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0 ||
            bounds.width < 2 || bounds.height < 2 || bounds.top > innerHeight || bounds.left > innerWidth ||
            bounds.bottom < 0 || bounds.right < 0 || clippedByAncestor(element, bounds) ||
            element.type === 'password') continue;
        const id = `pp-${targets.length + 1}`;
        element.setAttribute('data-genesia-target', id);
        const tag = element.tagName.toLowerCase();
        const type = (element.getAttribute('type') || '').toLowerCase();
        const textInput = (tag === 'input' && !['button', 'checkbox', 'radio', 'submit', 'reset', 'range', 'color', 'file'].includes(type)) ||
            tag === 'textarea' || element.isContentEditable;
        const actions = tag === 'select' ? ['click', 'select'] :
            textInput ? ['click', 'type'] : ['click', 'right_click'];
        const fingerprint = {tag};
        for (const attribute of ['id', 'data-testid', 'data-pl', 'data-pl-key', 'aria-label',
            'title', 'name', 'type', 'href', 'role', 'placeholder']) {
            const value = element.getAttribute(attribute);
            if (value) fingerprint[attribute] = value;
        }
        const visibleText = (element.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 160);
        if (visibleText) fingerprint.text = visibleText;
        const textLines = (element.innerText || '').split(/\r?\n/)
            .map(line => line.replace(/[\uE000-\uF8FF\u{F0000}-\u{FFFFD}\u{100000}-\u{10FFFD}]/gu, '')
                .trim().replace(/\s+/g, ' '))
            .filter(Boolean);
        const explicitName = element.getAttribute('aria-label') || element.getAttribute('title') ||
            element.getAttribute('placeholder');
        const name = (explicitName || textLines[0] || element.getAttribute('data-pl') || '')
            .trim().replace(/\s+/g, ' ').slice(0, 160);
        const description = explicitName ? '' : textLines.slice(1).join(' ').slice(0, 240);
        targets.push({id, name, description,
            disabled: Boolean(element.disabled || element.getAttribute('aria-disabled') === 'true'),
            x: Math.min(innerWidth, Math.max(0, bounds.left + bounds.width / 2)),
            y: Math.min(innerHeight, Math.max(0, bounds.top + bounds.height / 2)), fingerprint, actions});
        const mark = document.createElement('span');
        mark.setAttribute('data-genesia-mark', 'true');
        mark.textContent = id;
        Object.assign(mark.style, {position:'fixed', left:`${Math.max(0, bounds.left)}px`,
            top:`${Math.max(0, bounds.top)}px`, zIndex:'2147483647', color:'white', background:'#ba3030',
            font:'12px monospace', pointerEvents:'none'});
        document.body.appendChild(mark);
    }
    return targets;
}