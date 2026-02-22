prod_dial = null;
hyd_dial = null;
focus_dial = null;
post_dial = null;

document.addEventListener("DOMContentLoaded", function () {
    makeKnobs();
});

function makeKnobs() {
    prod_dial = createKnob('prod_dial');
    hyd_dial = createKnob('hydration_dial');
    focus_dial = createKnob('focus_dial');
    post_dial = createKnob('posture_dial');
}

function createKnob(parentDivID) {
    // Create knob element, 300 x 300 px in size.
    const knob = pureknob.createKnob(300, 300);

    // Set properties.
    knob.setProperty('angleStart', -0.75 * Math.PI);
    knob.setProperty('angleEnd', 0.75 * Math.PI);
    knob.setProperty('colorFG', '#f06161');
    knob.setProperty('trackWidth', 0.4);
    knob.setProperty('valMin', 0);
    knob.setProperty('valMax', 100);
    knob.setProperty('readonly', true);

    // Set initial value.
    knob.setValue(50);

    // Create element node.
    const node = knob.node();

    // Add it to the DOM.
    const elem = document.getElementById(parentDivID);
    elem.appendChild(node);

    return node;
}