# Camera-sounds add-on for Home Assistant

# THIS ADD-ON IS "Beta"

This project uses TensorFlow Lite and the
[YAMNet sound model](https://www.tensorflow.org/hub/tutorials/yamnet)
to characterize sounds deteced by  microphones on networked cameras.
*It does not record or keep any sound samples after analyzing them*. It
takes brief (see settings) samples using FFMPEG and scores sound types 
detected, based on a YAMnet's 520 sound classes.

The project relies on MQTT for communicating with Home Assistant.

Designed as a Home Assistant addon, this version follows
[Yamcam2](https://github.com/cecat/CeC-HA-Addons/tree/main/addons/yamcam2),
which is useful to monitor sound sources (microphones on cameras, or other
rtsp sources) to get a feel for what sounds your microphones are picking up.
Yamcam2 and this addon do the following:
1. Analyze sound (in ~1s chunks) using Yamnet, which produces scores for each
   of 521 sound classes.
2. Filter out all but the *top_k* sounds whose scores exceed *noise_threshold*.
3. Aggregate those *top_k* scoring sound classes into groups such as "people," "music",
   "insects," or "birds." This uses a custom yamnet_class_map.csv where each
   of the 521 native classes has been grouped and renamed as *groupname*.*classname*.
4. Assign a composite score to each group, based on the scores (that made the
   *top_k* cut) of the individual yamnet classes within that group.

Yamnet3 differs from Yamnet2 in the following ways:
1. Rather than polling sources by temporarily opening FFMPEG for a sample
   duration, we open a continous ffmpeg stream to each source, read and analyzed
   within a separate thread.
2. Instead of continually reporting what sound classes are being detected, we
   move toward something more like Frigate, where we report when a sound class
   forms a "sound event" that starts and ends.  We use three parameters
   (also in the config file) to define events, as outlined below.

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

### Create the Add-on Configuration File

Create a file in your Home Assistant directory */config* named
*microphones.yaml*. Here you will configure specifics including your MQTT broker address,
MQTT username and password, and RTSP feeds. These will be the same feeds you use
in Frigate (if you use Frigate), some of which may have embedded credentials
(so treat this as a secrets file). 

classes/scores reported.  Example:
'''
{
    "camera_name": "pondcam",
    "sound_class": "birds",
    "event_type": "start",
    "timestamp": "2024-10-03 16:46:29"
}
'''

#### Sample Configuration File

```
general:
  noise_threshold: 0.1          # Filter out very very low scores
  default_min_score: 0.5        # Default threshold for group scores (default 0.5)
  top_k: 10                     # Number of top scoring classes to analyze (default 10)
  use_groups: true              # Default true, report by group rather than the original
                                # YAMNet classes
  log_level: DEBUG              # Default INFO. In order of decreasing verbosity:
                                # DEBUG->INFO->WARNING->ERROR->CRITICAL 

mqtt:
  host: "x.x.x.x"               # Your MQTT server (commonly the IP addr of your HA server)
  port: 1883                    # Default unless you specifically changed it in your broker
  topic_prefix: "yamcam/sounds" # adjust to your taste
  client_id: "yamcam"           # adjust to your taste (a "3" will be appended to avoid
                                # colliding with Yamcam2 (which also uses this file) and
                                # confusing MQTT.
  user: "mymqttusername"        # your mqtt username on your broker (e.g., Home Asst server) 
  password: "mymqttpassword"    #         & password

# EVENTS (define 'event' parameters)
events:
  window_detect: 5              # Number of samples (~1s each) to examine to determine 
                                #   if a sound is persistent.
  persistence: 2                # Number of detections within window_detect to consider
                                #   a sound event has started.
  decay: 10                     # Number of waveforms without the sound to consider 
                                #   the sound event has stopped.


# SOURCES
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


# sound groups to listen for, and optional individual thresholds (will override
# reporting_threshold above in general settings). 
sounds:                     
  track:                    
    - people
    - birds
    - alert
  filters:
    people:
      min_score: 0.70
    birds:
      min_score: 0.70
    alert:
      min_score: 0.8

```

**General configuration variables**

- **noise_threshold**: Default 0.1 - Many sound classes will have very low scores, so we filter these 
out before processing the composite score for a sound group.

- **default_min_score**: Default 0.4 - When reporting to scores we ignore any groups with
scores below this value.

- **top_k**: YAMNet scores all 520 classes, we analyze the top_k highest scoring classes. However,
we ignore classes with confidence levels below *noise_threshold*.

- **use_groups**: See note below re modifying the sound class maps to group them.  Setting this
option to *false* will ignore these groupings and just report the native classes, however, they
will still be prepended with groupnames (which are not part of the original YAMNet mappings).

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

**Sound Event Parameters**

- **window_detect**: Number of samples (~1s each) to examine to determine if a sound is persistent.
- **persistence**:   Number of detections within window_detect to consider a sound event has started.
- **decay**:         Number of waveforms without the sound to consider the sound event has stopped.

**Sounds and Filters**

These are structured similarly to Frigate configuration. Nothing will be reported if no sound
groups are listed here. If no min_score is set for a group, the general setting *default_min_score* is used.
are not set.

The sounds yaml group allows you to select the specific sound groups you want to track
and (optionally) set thresholds for each.  Available sound groups are:
- aircraft
- alert (e.g., sirens, alarms, ringtones, loud pops...)
- animals
- birds
- construction (e.g., banging, sawing...)
- insects
- music
- people
- vehicles
- weather

More on sound groups below.

## Modified YAMNet Sound Class Scheme for Convenience Integrating with Home Assistant.

In the addon's directory is a *files* subdirectory, which contains the YAMNet *tflite* model
and a CSV file that maps YAMNet output codes to the human-readable names for those classes.
These are available at the
[TensorFlow hub](https://www.kaggle.com/models/google/yamnet/tfLite/classification-tflite/1?lite-format=tflite&tfhub-redirect=true).

The *yamnet_class_map.csv* used here is modified (without losing the original class names).
Yamnet has a whopping 521 sound classes,
so if we are looking for human-related sounds there are
many distinct classes (e.g., *giggle, hiccup, laughter, shout, sigh,* not
to mention *speech, crowd, or sneeze*...). Similarly, if we want to detect that
music is playing there are many many related classes (*reggae, rimshot, rock and roll,
strum, tabla*...).

For this addon to be useful for Home Assistant automations it seemed useful
to group these 521 classes.
This is done by using a modified version of *yamnet_class_map.csv* that
prepends a group name to each of the 521 sound class names.
For example, the classes *fiddle*, *snareDrum*, and *Middle Eastern Music*
are replaced with *music.fiddle, music.snareDrum* and * music.middleEasternMusic*;
and the classes *Tire Squeel*, *Motorcycle*, and
*Vehicle Horn Honking, Car Horn Honking* are replaced with 
*vehicles.tireSqueel*, *vehicles.motorcycle*, and
*vehicles.vehicleHornCarHornHonking*

This allows automations to check for group names rather than lists of 30 or 40
sound classes that might be related to what we are wanting to detect (e.g., 
human activity, traffic sounds, etc.).

The code pulls the *top_k* classes with the highest scores (assuming there are 
at leaste *top_k* classes that exceed *noise_threshold*), then calculates a
group score from these.
For example, if there are three classes from the *music* group with scores in the top_k,
the composite (i.e., group) score is calculated as follows:
- If the highest score (*max_score*) among those in the same group >= 0.7,
group_score = max_score
- Else group_score = max_score + 0.05(group_count), where group_count is the number of classes from that group are in the top_k scores. (group_score is capped at 0.95).


## Tech Info

- Languages & Frameworks:
  - Python
  - Home Assistant Framework
- Key Dependencies
  - MQTT

This addon uses MQTT to communicate with Home Assistant. It's been tested
with the open source
[Mosquitto broker](https://github.com/home-assistant/addons/tree/master/mosquitto) 
from the *Official add-ons* repository.

### Other Notes

This add-on has only been tested using RTSP feeds from Amcrest and UniFi (via NVR)
cameras. It's been tested on Home Assistant running on a Raspberry Pi 4 and on
an Intel Celeron (neither of which support Advanced Vector
Extensions (AVX) instructions).

