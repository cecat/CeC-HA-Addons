
# Changelog

## 0.2.1
- Append "2" to the mqtt client ID so that one can run both yamcam2 and
  yamcam3 using the same /config/microphones.yaml config file without
  having two add-ons using the same client ID (confusing MQTT).

## 0.2.0
- Re-publish in CeC-HA-Addons store.
- Overhauled README to be more helpful

## 0.1.2
- Fixed aggregation of segments for sample sizes >0.975s YAMNet max.  Added
  'aggregation' config variable to select between mean, sum, and max of class values across
  segments. (with logic to add more later if desired).
- Added config variable to select between aggregating classes into groups for reporting
  or ignoring groups and reporting native classes (albeit they will still be prepended
  with group name unless one replaces /files/yamnet_class_map.csv with the original
  which is included as /files/yamnet_class_map_ORIG.csv.
- Clarified timing in README regarding sample_interval
- Implemented top_k and added report_k where top_k is the number of highest-scoring classes
  to analyze and report_k is the number of highest-scoring classes (or groups) to report.
- Cleaned up debug log statements to lean further toward debug help for users vs. debug while
  developing/testing code.

## 0.1.1
- Re-engineered moving external functions out of main code.
- Fixed issue (ffmpeg wedging, fixed by specifying audio channel) with NVR RTSP path

## 0.1.0
- start to re-engineeer to make code modular, moving functions
  and various settings to a yamcam_functions.py file (will take some doing)

## 0.0.l
- remove all input filtering, etc. as it prevented the model from correctly 
  identifying anything.  

## 0.0.k
- add scipy for filtering input waveform to remove white noise before classifying.
- in this version we'll start with a Wiener filter
  (not to be confused with a "whiner" filter which would have many uses in other contexts)

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

