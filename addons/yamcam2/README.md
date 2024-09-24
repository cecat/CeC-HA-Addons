# Camera-sounds add-on for Home Assistant

---

This project uses TensorFlow Lite and the
[YAMNet sound model](https://www.tensorflow.org/hub/tutorials/yamnet)
to characterize sounds deteced by  microphones on networked cameras.
*It does not record or keep any sound samples after analyzing them*. It
takes brief (see settings) samples using FFMPEG and scores sound types 
detected, based on a YAMnet's 520 sound classes.
(This is version2 - previous version (yamcam) was an experiment that has here
been nearly completely rewritten.)


## How to Use

### Install the Add-on on your Home Assistant Server

There are two ways to integrate this add-on with your Home Assistant system:
via the Add-on store or manual installation as a local add-on.  The Add-on
store is by far the most convenient and easiest for obtaining fixes/updates.

1. Add-on Store Installation:

- Go to **Settings** --> **Add-ons** and click the blue **ADD-ON-STORE** button
at bottom right.
- Click the three vertical dots icon at upper right of the Add-On Store screen.
- Paste *https://github.com/cecat/CeC-HA-Addons* into the Add field at the bottom
of the **Manage add-on repositories** pop-up window and hit the blue **ADD** at right.
- The **CeC Home Assistant Add-ons** repository will appear in your Add-on Store; 
Select the **YAMNet Camera Sounds** add-on.


2. Manual Installation:

- Download this repository (*https://github.com/cecat/CeC-HA-Addons/tree/main/addons/yamcam*)
- Place it in your */addons/local* directory of your Home Assistant Server.
- On your Home Assistant, go to **Settings** --> **Add-ons** and click the reload 
(arrow circling a clock) icon in the upper right of that page.  The add-on should appear.


### Set up Configuration for the Add-on

For each sound source, at each reporting interval,
we send a MQTT  message to HA of the form "Class1 (score1), Class2 (score2)..."
This is not very convenient to parse from the HA side. I'm experimenting with
the best way to format this (Frigate messages are pretty detailed JSON
which yields very powerful HA capabilities, but I'm aiming for something
simpler, as this is a simpler capability).

This addon uses MQTT to communicate with Home Assistant. It's been tested
with the open source
[Mosquitto broker](https://github.com/home-assistant/addons/tree/master/mosquitto) 
from the *Official add-ons* repository.

### Create the Add-on Configuration File

Create a file in your Home Assistant directory */config* named
*microphones.yaml*. Here you will configure specifics including your MQTT broker address,
MQTT username and password, and RTSP feeds. These will be the same feeds you use
in Frigate (if you use Frigate), some of which may have embedded credentials
(so treat this as a secrets file). 

The config file also includes many knobs you can use to customize how the addon
functions.  These are explained below.

#### Sample Configuration File

```
general:
  sample_interval: 15        # Sampling interval (seconds) (default 15)
  sample_duration: 3         # Sound sample length (seconds) (default 3) 
  top_k: 10                  # Number of top scoring classes to analyze (default 10)
  report_k: 3                # Number of top scoring groups or classes to report (default 3)
  reporting_threshold: 0.5   # Reporting threshold for sound class scores (default 0.4)
  group_classes: true        # Default true, report by group rather than the original YAMNet classes
  aggregation_method: max    # Use max (default) or mean to pool scores across segments of a collected sample
  log_level: DEBUG           # Default INFO. In order of decreasing verbosity:
                             # DEBUG->INFO->WARNING->ERROR->CRITICAL 
mqtt:
  host: "x.x.x.x"            # Your MQTT server (commonly the IP addr of your HA server)
  port: 1883                 # Default unless you specifically changed it in your broker
  topic_prefix: "sounds"     # adjust to your taste
  client_id: "yamcam"        # adjust to your taste
  user: "mymqttusername"     # your mqtt username on your broker (e.g., Home Asst server) 
  password: "mymqttpassword" #         & password

# examples of Amcrest and UniFi NVR camera rtsp feeds
cameras:
  doorfrontcam:
    ffmpeg:
      inputs:
      - path: "rtsp://user:password@x.x.x.x:554/cam/realmonitor?channel=1&subtype=1"
  frontyardcam:
    ffmpeg:
      inputs:
      - path: "rtsp://x.x.x.x:7447/65dd5a1900f4cb70dffa2143_1"
```

**General configuration variables**

- **sample_interval**: Wait time (seconds) between cycling through the sound
sources (ffmpeg, analyze, calculate scores, report via MQTT) so sample_interval
for n cameras (on a low-end Celeron CPU it takes about 2s to process audio and report) is actually
(sample_duration+2) * n + sample_interval.  So three with 3s *sample_duration* will take about
15s to process, and if *sample_interval* is 15 then it each camera will get sampled about once
every (3+2)*3 + 15 = 30s.

- **sample_duration**: Sound sample length (seconds) (default 3). YAMNet operates on 16 KHz 
frames, maximum 15,360 samples -- so it operates on 0.96s duration frames.  To analyze across
longer durations we segment the waveform into 0.96s frames with 50% overlap, then combine the
scores across the segments by taking the max of scores for each class.

- **top_k**: YAMNet scores all 520 classes, we analyze the top_k highest scoring classes.

- **report_k**: After analyzing top scores, we report the report_k highest scoring
classes (generally a subset of top_k).

- **reporting_threshold**: Default 0.4 - When reporting to scores we ignore any classes with
scores below this value (from 0.0 to 1.0).

- **group_classes**: See note below re modifying the sound class maps to group them.  Setting this
option to *false* will ignore these groupings and just report the native classes, however, they
will still be prepended with groupnames (which are not part of the original YAMNet mappings).

- **aggregation_method**: YAMNet analyzes 0.96s samples. For longer *sample_duration*
we divide the waveform into multiple segments, each 0.96s, overlapped by 50%.  The method
specified here is used to create a score for the collection of segments. The choices are 
*mean* or *max*. 

- **log_level**: Level of detail to be logged. Levels are
DEBUG->INFO->WARNING->ERROR->CRITICAL
in order of decreasing verbosity.

**MQTT configuration variables**

- **host**: Typically this will be the hostname or IP address for your Home Assistant server.

- **port**: MQTT by default uses port 1883.

- **topic_prefix**: Should be of the form "abc" or "foo/bar" according to how you manage your MQTT
usage in Home Assistant.  The addon will append the name of the camera (from your
configuration file), with the detected sound classes as the payload to this topic.

- **client_id**: This is unique to the add-on for managing MQTT connections and traffic.

- **user**: Here you will use the username/login on your server (e.g., that you set up for MQTT).

- **password**: The password to the username/login you are using as *user*.

## Modified YAMNet Sound Class Scheme for Convenience Integrating with Home Assistant.

In the addon's directory is a *files* subdirectory, which contains the YAMNet *tflite* model
and a CSV file that maps YAMNet output codes to the human-readable names for those classes.
These are available at the
[TensorFlow hub](https://www.kaggle.com/models/google/yamnet/tfLite/classification-tflite/1?lite-format=tflite&tfhub-redirect=true).

The *yamnet_class_map.csv* used here is modified (without losing the original class names).
Yamnet has a whopping 521 sound classes,
so if we are looking for human-related sounds there are
many distinct classes (e.g., giggle, hiccup, laughter, shout, sigh, not
to mention speech, crowd, or sneeze...). Similarly, if we want to detect that
music is playing there are many many related classes (reggae, rimshot, rock and roll,
strum, tabla...).

The purpose of this addon is to use Home Assistant automations to
potentially act on detecting broad ranges of things (like human activity
in general, which might trigger turning on lights). Alternatively,
one might wish to track the use of a space over time (how often do
we use this room, or play music).  For this purpose, I've created a
version of *yamnet_class_map.csv* that prepends a grouping to each sound
class.  The group name is prepended to the YAMNet class name. Thus,
for example, the classes *music*, *snareDrum*, and *Middle Eastern Music*
are replaced with *music.snareDrum*, *music.middleEasternMusic*,
and the classes *Tire Squeel*, *Motorcycle*, and
*Vehicle Horn Honking, Car Horn Honking* are replaced with 
*vehicles.tireSqueel*, *vehicles.motorcycle*, and
*vehicles.vehicleHornCarHornHonking*

This allows automations to check for group names rather than lists of 30 or 40
sound classes that might be related to what we are wanting to detect (e.g., 
human activity, traffic sounds, etc.).

The code only pulls the n classes with the highest scores (n = *top_k* in the 
*microphones.yaml* configuration file) and then calculates a group score from
these.  For example, if there are three *music_classname* scores in the top_k,
the group score combines them as follows:
- If the highest score (*max_score*) among those in the same group >= 0.7,
group_score = max_score
- Else group_score = max_score + 0.05(group_count), where group_count is the number of classes from that group are in the top_k scores. (group_score is capped at 0.95).

Flipping the config variable *group_classes* to *false* will result in reporting
all *top_k* classes without grouping them or calculating group scores.  They will
still be prepended with *group.*.  To go fully native YAMNet in terms of class
names, the original yamnet class map is included in */files* so one can replace
*files/yamnet_class_map.csv* with the original (*files/yamnet_class_map_ORIG.csv*).

## Tech Info

- Languages & Frameworks:
  - Python
  - Home Assistant Framework
- Key Dependencies
  - MQTT

### Other Notes

This add-on has only been tested using RTSP feeds from Amcrest and UniFi (via NVR)
cameras. It's been tested on Home Assistant running on a Raspberry Pi 4 and on
an Intel Celeron (neither of which support Advanced Vector
Extensions (AVX) instructions).

