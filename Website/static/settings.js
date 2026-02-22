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
        } else if (el.type === 'text' || el.type === 'email' || el.type === 'password') {
            json[el.name] = el.value;
        }
    });

    return JSON.stringify(json);
}
