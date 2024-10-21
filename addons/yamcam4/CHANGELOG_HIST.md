
# Changelog

## 1.0.0
- Eliminated the *exclude_groups* list as we have a *sounds*->*track* list already,
  so any group not in that list will be excluded (previously all groups/classes were
  logged irrespective of the *track* list).
- Stopped logging classes from excluded groups. Mostly because the CSV was primarily "silence" which
  meant huge files and (more importantly) a vast majority of rows being silence (not useful).
## 0.3.5
- Added warning log messages and logic (including default values) to handle
  various FFmpeg failure modes for errant source RTSP paths, such as missing
  credentials, wrong port, etc.
- Added sound events to the sound_log file, so it now has 8 columns (see 
  README).
- Check for and set to default booleans with spelling errors (like setting
  to "treu" or "flse").
- Updated starter/sample microphones.yaml config file with recent changes
  and additions.
- Removed the filename field in log messages (not needed) to clean them up a bit.

## 0.3.4
- Moved location of logs (debug and sound) to /media/yamcam.  Those running
  Frigate will already have /media but /media/yamcam will be created if it
  does not already exist.
- .log files (debug logging) and .csv files (sound logging) created at
  add-on startup with filenames yyyymmdd-hhmm rather than appending to
  one mamoth file.
- Informational warning if there is more than 100MB of .log or .csv files
  in /media/yamcam (in case the user cares).
- Initial logic to check for and handle mistakes in microphones.yaml config
  file, such as missing mqtt or camera settings.

## 0.3.3
- Added a configuration boolean, sound_log, to create a csv with all group
  and class detections and scores.  CSV has 6 columns, 1 row per class or
  group detected (i.e, with score >noise_threshold):
  date_time, camera_name, group_name, group_score, class_name, class_score
- Removed the -logfile boolean from README but it's still implemented, and
  could be useful to diagnose issues that are intermittent (as these are
  log messages including errors.

## 0.3.2
- Cleaned up logging
- Added a logfile capability for longitudinal analysis of sound activity
- Implemented *sound events* as the reportable (via MQTT) measure, with 
  start and end messages and settable parameters to define when to determine
  an *event* has begun or ended.
- Masked out FFMPEG stderr traffic from the rest of DEBUG logging, since FFMPEG
  is verbose and has no codes to indicate the nature of its messages.
- For logging, designed the INFO level to just track sound events while DEBUG
  level will log all sound classes, groups, and events.
- Added a summary report that every *summary_interval* minutes logs (INFO level)
  how many sound events (and what sound groups) were detected for each source.

## 0.3.1
- Overhaul how we use/report yamnet scores/detections.  In this version,
  we switch from capturing sound, analyzing, and reporting every n second intervals
  to continously streaming, and rather than continue periodically reporting everything
  (yamcam2 is good for that) this one supports (a) specifying which sound groups to
  detect, with individual score thresholds, and (b) using three parameters to define
  windows for sound "events."  This version, then, only reports when a sound event
  starts and when a sound event ends.
- To specify groups of interest, the same yaml syntax is used as in Frigate
- To determine how to define sound "events" that start and stop, we use three
  config variables (see README.md):
  - window_detect - the window (seconds) within which we decide a sound is "present"
  - persistence - the number of detections within window_detect for a given 
    sound group to determine that it's an event of interst.
  - window_detect - once we decide a sound event has begun, how many seconds 
    we wait, where we do not detect the sound, before deciding that the event has
    ended.
- mqtt_client_id from microphones.yaml will have a '3' appended to avoid colliding
  with yamcam2 (which will have '2' appended) since we use the same microphones.yaml
  file.

## 0.3.0
- Implement continuous streaming and threads

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

