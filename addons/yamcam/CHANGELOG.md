
# Changelog

## 0.0.b
- make log messages more useful

## 0.0.a
- went back to working code, re-implemented the error handling
  previous attempt introduced too much complexity.
- check for yaml errors and, rather than fail...
- provide log messages for cases where there are errors in the user's
  config (/config/microphones.yaml), or if it's missing.

## 0.0.9
- check for yaml errors and, rather than fail...
- provide log messages for cases where there are errors in the user's
  config (/config/microphones.yaml), or if it's missing.

## 0.0.8
- normalize the volume levels to see if this helps yamnet performance

## 0.0.7
- handle unreachable camera errors nicely, try 3x before giving up
- let the user know what rtsp feed is unreachable

## 0.0.6
- move sampling frequency and score threshold to /config/microphones.yaml

## 0.0.5
- lots of experiments, now using Tensorflow Lite
- this version requires pre-downloading tflite and the yamnet class csv

## 0.0.4
- add MQTT connect and send a test message

## 0.0.3
- add read from config file and set up MQTT params (log them)

## 0.0.2
- minimum functionality test (just test logging)

## 0.0.1
- initial code

