document.addEventListener("DOMContentLoaded", function () {
    loadValues();
});

document.getElementById('settingsModal')
  .addEventListener('shown.bs.modal', loadValues);

const settings_button = document.getElementById('settings_button');

settings_button.addEventListener('click', async _ => {
  try { 
    const response = await fetch('/update_settings', {
      method: 'post',
      body: get_form_as_json('settings_form')
    });
    console.log('Completed!', response);
  } catch(err) {
    console.error(`Error: ${err}`);
  }
});

const profile_button = document.getElementById('profile_button');

profile_button.addEventListener('click', async _ => {
  try {
    const response = await fetch('/update_profile', {
      method: 'post',
      body: get_form_as_json('profile_form')
    });
    console.log('Completed!', response);
  } catch(err) {
    console.error(`Error: ${err}`);
  }
});

function get_form_as_json(form_name){
    const form = document.getElementById(form_name);

    const formElements = Array.from(form.elements);

    // Build JSON object
    const json = {};
    formElements.forEach(el => {
        if (el.type === 'checkbox') {
            json[el.name] = el.checked;
        } else if (el.type === 'text' || el.type === 'email' || el.type === 'password' || el.tagName ==='SELECT') {
            json[el.name] = el.value;
        }
    });

    return JSON.stringify(json);
}

function loadValues()
{
    fetch("/get_settings",
    {
        method: "GET"
      })
        .then((response) => response.json())
        .then((json) => {
            console.log(json);  // log it here instead
            document.getElementById("systemToggle").checked = json.system_enabled;
            document.getElementById("productivityToggle").checked = json.track_productivity;
            document.getElementById("focusToggle").checked = json.track_focus;
            document.getElementById("hydrationToggle").checked = json.track_hydration;
            document.getElementById("postureToggle").checked = json.track_posture;
            document.getElementById("voice_selection").value = json.selected_voice;
        });
}
