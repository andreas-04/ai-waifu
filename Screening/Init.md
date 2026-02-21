# Screening

## Objective 

Create an application to monitor a users screen. 

Every period of time, take screenshots, pull insights to what the user if doing. 

Using the insights, compare them to the list of allowed applications or inform if a user is being productive or not. This criteria will be set by the user. 

## TODO

Allow monitoring of a users screen. 

capture the screen. 

Look into using: 

```javascript
navigator.mediaDevices.getDisplayMedia({
  video: true,
  audio: false
});
```

use a websocket and send this to a go backend that has the websocket open. 

Could make a websocket to stream the current state of the application. 


take screenshots every x time

OCR

classify using facebook/bart-large-mnli