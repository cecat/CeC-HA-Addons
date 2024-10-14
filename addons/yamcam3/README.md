# Camera-sounds add-on for Home Assistant

This add-on is a work in progress.  Please report any issues
[here](https://github.com/cecat/CeC-HA-Addons/issues). 

This project uses TensorFlow Lite and the
[YAMNet sound model](https://www.tensorflow.org/hub/tutorials/yamnet)
to characterize sounds deteced by  microphones on networked cameras.
*It does not record or keep any sound samples after analyzing them*. It
continually takes 0.975s samples from RTSP feeds, using FFMPEG, and
pushes these samples to the YAMNet sound classifier model, which
returns scores for each of its 521 sound classes.

The project uses MQTT to communicate *sound events* to  Home Assistant,
where the parameters for determining the start and stop of a sound event
are configurable.

The add-on does the following (*italics* parameters are configurable)::

1. Analyze sound (in 0.975s chunks) using YAMNet, which produces scores for each
   of 521 sound classes. A **score** is YAMNet's certainty, from 0 to 1, that
   the sound class is present.
2. Filter out all but the *top_k* sounds whose scores exceed *noise_threshold*.
3. Aggregate those *top_k* scoring sound classes into groups such as "people," "music",
   "insects," or "birds." This uses a modified yamnet_class_map.csv where each
   of the 521 native classes has been grouped and renamed as groupname.classname.
4. Assign a composite score to each group with classes that appear in the *top_k*,
   based on the individual scores of the classes from that group that are detected
   in the *top_k*. 
5. Detects the start and end of "sound events" defined by three configurable
   parameters (see configuration instructions below).
6. Reports sound event start/stop to Home Assistant via MQTT.

For longitudinal analysis, a *sound_log* can be created with all *top_k*
classes/scores, and associated groups/scores.

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

- Download this repository (*https://github.com/cecat/CeC-HA-Addons/tree/main/addons/yamcam3*)
- Place it in your */addons/local* directory of your Home Assistant Server.
- On your Home Assistant, go to **Settings** --> **Add-ons** and click the reload 
(arrow circling a clock) icon in the upper right of that page.  The add-on should appear.

### Create the Add-on Configuration File

Create a file in your Home Assistant directory */config* named
*microphones.yaml*. Here you will configure specifics including your MQTT broker address,
MQTT username and password, and RTSP feeds. These will be the same feeds you use
in Frigate (if you use Frigate), some of which may have embedded credentials
(so treat this as a secrets file). 

If you are a Frigate user, you can copy/past your camera names and paths
from your *frigate.yml* file.  Similarly, you will use the *mqtt* host and port
from your *frigate.yml* file with *topic_prefix* and *client_id* unique to *this* add-on.
The *sounds:* section also follows the same syntax as Frigate's detection objects and optional 
individual min_score thresholds (which override *default_min_store* for the
associated groups).

#### Sample Configuration File

You can get a starter configuration file and just fill in your MQTT and camera details 
[here](https://github.com/cecat/CeC-HA-Addons/blob/main/addons/yamcam3/microphones.yaml).
Below is an example showing RTSP paths for an Amcrest camera and for a UniFi camera (via
its NVR).

```
general:
  noise_threshold: 0.1       # Filter out very very low scores
  default_min_score: 0.5     # Default threshold for group scores (default 0.5)
  top_k: 10                  # Number of top scoring classes to analyze (default 10)
  log_level: INFO            # Default INFO. In order of decreasing verbosity:
                             # DEBUG->INFO->WARNING->ERROR->CRITICAL 
  sound_log: false           # Create a CSV with all sound group and class scores over time
  ffmpeg_debug: false        # Log ffmpeg stderr (a firehose - includes errors and info)
                             #   Must also have log_level set to DEBUG
  summary_interval: 15       # log a summary every n min showing the sound groups detected.
  exclude_groups:            # Groups we don't want to report (or log), e.g., 
    - group1                 #   the 'silence' group in particular can be noisy...
    - group2

mqtt:
  host: "x.x.x.x"               # Your MQTT server (commonly the IP addr of your HA server)
  port: 1883                    # Default unless you specifically changed it in your broker
  topic_prefix: "yamcam/sounds" # adjust to your taste
  client_id: "yamcam"           # adjust to your taste 
  user: "mymqttUsername"        # your mqtt username on your broker (e.g., Home Asst server) 
  password: "mymqttPassword"    #         & password

events:
  window_detect: 5              # Number of samples (~1s each) to examine to determine 
                                #   if a sound is persistent.
  persistence: 2                # Number of detections within window_detect to consider
                                #   a sound event has started.
  decay: 10                     # Number of samples without the sound to determine that
                                #   the sound event has stopped.

cameras:
  doorfrontcam:
    ffmpeg:
      inputs:
      - path: "rtsp://user:password@x.x.x.x:554/cam/realmonitor?channel=1&subtype=1"
  frontyardcam:
    ffmpeg:
      inputs:
      - path: "rtsp://x.x.x.x:7447/65dd5a1900f4cb70dffa2143_1"

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

#### Configuration Parameters

**General**

- **noise_threshold**: Default 0.1 - Many sound classes will have very low scores, so we filter these 
out before processing the composite score for a sound group.
- **default_min_score**: Default 0.4 - When reporting to scores we ignore any groups with
scores below this value.
- **top_k**: YAMNet scores all 520 classes, we analyze the top_k highest scoring classes,
ignoring classes with scores below *noise_threshold*.
- **log_level**: Level of detail to be logged. Levels are
DEBUG->INFO->WARNING->ERROR->CRITICAL
in order of decreasing verbosity.
- **sound_log**: Creates or appends to a sound logfile in */config* for longitudinal analysis. 
The file is a csv with date/time, camera_name, group, group_score, class, class_score
(one class *or* group per line)
- **ffmpeg_debug**: Logs all messages to ffmpeg stderr, which have no codes nor does ffmpeg
differentiate between info and errors - so it's a firehose (coming from all n sources)
- **exclude_groups**: An optional list of groups to exclude from event detection and logging.
The *silence* group is quite frequently detected, for instance, and is a bit redundant relative to
nothing being reported.  See **Sounds and Filters** below for a list of groups.

**MQTT configuration variables**

- **host**: Typically this will be the hostname or IP address for your Home Assistant server.
- **port**: MQTT by default uses port 1883.
- **topic_prefix**: Should be of the form "abc" or "foo/bar" according to how you manage your MQTT
usage in Home Assistant.  The addon will append the name of the camera (from your
configuration file), with the detected sound classes as the payload to this topic.
- **client_id**: This is unique to the add-on for managing MQTT connections and traffic.
- **user**: Here you will use the username/login on your server (e.g., that you set up for MQTT).
- **password**: The password to the username/login you are using as *user*.

**Events**

- **window_detect**: Number of samples (~1s each) to examine to determine if a sound is persistent.
- **persistence**:   Number of detections within window_detect to consider a sound event has started.
- **decay**:         Number of waveforms without the sound to consider the sound event has stopped.

**Cameras**

- This is where you name your cameras (assuming they have microphones) and specify the RTSP path.
  It is always a good idea to make sure your paths are correct by opening them with an app like
  VLC Media Player.  For debugging you can also configure just with the problem camera and
  set log_level=DEBUG and ffmpeg_debug=true, then watch the Log (navigate to the add-on in Home
  Assistant and after hitting *Start* in the *Info* view, select *Log* view at the top of the window.

**Sounds**

These are structured similarly to Frigate configuration. *Nothing will be reported if no sound
groups are listed here.* If no *min_score* is set for a group, the *default_min_score*
(General parameters above) is used.

Available sound groups are:
- aircraft
- alert (e.g., sirens, alarms, loud bangs...)
- animals
- birds
- construction (e.g., banging, sawing...)
- insects
- music
- people (e.g., laughter, coughing, speaking, ringtones, doorbells...)
- silence
- vehicles
- weather

More on sound groups below.

## Modified YAMNet Sound Class Scheme for Convenience Integrating with Home Assistant.

In the addon's directory is a *files* subdirectory, which contains the YAMNet *tflite* model
and a CSV file that maps YAMNet output codes to the human-readable names for those classes.
These are available at the
[TensorFlow hub](https://www.kaggle.com/models/google/yamnet/tfLite/classification-tflite/1?lite-format=tflite&tfhub-redirect=true).

The *yamnet_class_map.csv* used here is modified (without losing the original class names).
Yamnet has a whopping 521 sound classes, so if we are looking for human-related sounds there are
many related classes (e.g., *giggle, hiccup, laughter, shout, sigh,* not
to mention *speech, crowd, or sneeze*...). Similarly, if we want to detect that
music is playing there are over 150 related classes (*reggae, rimshot, rock and roll,
strum, tabla*...).

For this addon to be useful for Home Assistant automations it seemed reasonable 
to group these 521 classes, so that, for example, an automation can check for "people" rather than
all 60-80 classes related to people.  The grouping is implemented by using a modified version
of *yamnet_class_map.csv* that prepends a group name to each of the 521 sound class names.
For example, the classes *fiddle*, *snareDrum*, and *Middle Eastern Music*
are replaced with *music.fiddle, music.snareDrum* and * music.middleEasternMusic*;
and the classes *Tire Squeel*, *Motorcycle*, and
*Vehicle Horn Honking, Car Horn Honking* are replaced with 
*vehicles.tireSqueel*, *vehicles.motorcycle*, and
*vehicles.vehicleHornCarHornHonking*

Read more about groupings (and how you can customize)
[here](https://github.com/cecat/CeC-HA-Addons/tree/main/addons/yamcam3/files).

The add-on pulls the *top_k* classes with the highest scores (assuming there are 
at least *top_k* classes that exceed *noise_threshold*), then calculates a
group score from these.  The composite (i.e., group) score is calculated as follows:
- If the highest score (*max_score*) among those in the same group >= 0.7,
group_score = max_score
- Else group_score = max_score + 0.05(group_count), where group_count is the
number of classes from that group are in the top_k scores. 
- group_score is capped at 0.95.


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

