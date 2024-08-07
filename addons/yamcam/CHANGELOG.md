
# Changelog

## 0.0.j
- use max pooling to combine the scores of the segments

## 0.0.i
- divide our audio sample into yamnet-sized segments, slightly overlapping
  and analyze the longer duration rather than just trimming the whole thing 
  to 0.975s.

## 0.0.h
- remove waveform normalization, as it may have killed our accuracy

## 0.0.g
- Improve the grouping but keeping the entire original display_name for the
  class, but compressing it into a string with camelCase.
- you thought I was using hex

## 0.0.f
- Improved the grouping scheme, so that rather than losing the original class
  name (e.g., "Honk" and "Hoot" are both in my "birds" group, but I'd like
  to know if it's a goose or an owl, so rather than the original scheme
  reporting "bird" we now report "bird.honk" or "bird.hoot"

## 0.0.e
- Cleaned up, made debug messages more helpful

## 0.0.d
- added 4th column to yamnet_class_map.csv to group classes into a smaller
  number of 'super-classes' such as "people," "bird," "weather," or "vehicle."

## 0.0.c
- set logging level (verbosity) in /config/microphones.yaml (defualt INFO)
- log the individual classes found only in debug mode; in info just 
  log what is reported (i.e., score above reporting_threshold)

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

