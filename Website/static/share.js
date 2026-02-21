async function share() {
  const stream =
    await navigator.mediaDevices.getDisplayMedia({
      video: true
    });

  const video = document.createElement("video");
  video.srcObject = stream;
  await video.play();

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");

  setInterval(async () => {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    ctx.drawImage(video, 0, 0);

    canvas.toBlob(async blob => {
      const form = new FormData();
      form.append("image", blob);

      await fetch("/upload", {
        method: "POST",
        body: form
      });
    }, "image/jpeg");

  }, 3000);
}
