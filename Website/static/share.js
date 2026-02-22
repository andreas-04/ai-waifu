let intervalId = null;
let stream = null;

async function share() {
  const mediaStream =
    await navigator.mediaDevices.getDisplayMedia({
      video: true
    });

  stream = mediaStream;

  const video = document.createElement("video");
  video.srcObject = stream;
  await video.play();

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");

  intervalId = setInterval(async () => {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    ctx.drawImage(video, 0, 0);

    canvas.toBlob(async blob => {
      const form = new FormData();
      form.append("image", blob);

      const response = await fetch("/upload", {
        method: "POST",
        body: form
      });
      
      const data = await response.json();
      console.log(`Label: ${data.label}, Probability: ${data.probability}, Productivity Score: ${data.productivity_score}`);
      
      // Dispatch event so frontend can display the result
      const event = new CustomEvent('classificationResult', { 
        detail: { label: data.label, probability: data.probability, productivity_score: data.productivity_score } 
      });
      
      window.dispatchEvent(event);
    }, "image/jpeg");

  }, 3000);
}

// Get the input element and the status text element
const toggleInput = document.getElementById('productivityToggle');

function turnOffFunction() {
  // Stop the interval
  if (intervalId !== null) {
    clearInterval(intervalId);
    intervalId = null;
  }

  // Stop all tracks in the stream
  if (stream !== null) {
    stream.getTracks().forEach(track => track.stop());
    stream = null;
  }
}

// Add an event listener for the 'change' event
    toggleInput.addEventListener('change', () => {
      if (toggleInput.checked) {
        share()
      } else {
    // Optional: Run this function when the toggle is 'off' (unchecked)
        turnOffFunction();
  }
});