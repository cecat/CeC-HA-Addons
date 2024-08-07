# Camera-sounds add-on for Home Assistant
CeC
July 2024

---

### This is still a work in progress
It's basically working but I am still finding issues to fix...

Use TensorFlow Lite and the YAMNet sound model to characterize 
sounds deteced by  microphones on remote cameras.
It's not recording to keep anything, just taking 1s samples periodically and classifying
the sound, ideally to be able to detect people sounds, traffic sounds, storms, etc.
I was motivated by an interest in being able to detect that people are hanging out,
or the lawn was being mowed, even if the action is outside of the camera's field of
view.  Detecting a tornado 
warning siren migth not be a bad thing either.

This add-on has only been tested using RTSP feeds from Amcrest
cameras and moreover on a Raspberry Pi 4 and an Intel Celeron
(neither of which support Advanced Vector
Extensions (AVX) instructions), so it's far from proven.  It's not yet clear
to me that this will be useful in the end but it is worth a try.

## Installing
Be patient the first time you install...  We are pulling a very large pre-built
image (~600MB) for the initial build, so it could easily take 15 minutes for the
first build.  Subsequent updates, unless major, will build without re-downloading.
(I will try to improve this...  right now just going for functionality)

## Using and Configuring this Add-on

For each sound source, at each reporting interval,
we send a MQTT  message to HA of the form "Class (score), Class (score)..."
This is not very convenient to parse from the HA side. I'm experimenting with
the best way to format this (the Frigate messages are pretty detailed JSON
which yields very powerful HA capabilities, but I'm aiming for something
simpler, as this is a simpler capability).

0. This addon assumes you are running a MQTT broker already. This code
has (only) been tested with the open source
[Mosquitto broker](https://github.com/home-assistant/addons/tree/master/mosquitto) 
from the *Official add-ons* repository.

1. Create a file -  *microphones.yaml* - with specifics regarding your MQTT broker address,
MQTT username and password, and RTSP feeds. These will be the same feeds you use
in Frigate (if you use Frigate), which may have embedded credentials
(so treat this as a secrets file). If you want to adjust the sampling and/or
reporting frequency, or the minimum score, you can do this in *microphones.yaml*.
This configuration file will look something like below. Put this file into */config*.

```
general:
  sample_interval: 15       # Sampling interval (seconds)
  reporting_threshold: 0.4  # Reporting threshold for sound type scores
  log_level: INFO           # Change to WARNING, ERROR, CRITICAL for increasing verbosity
  top_k: 3                  # Number of top scoring classes to report


mqtt:
  host: "x.x.x.x"
  port: 1883
  topic_prefix: "HA/sensor" # adjust to your taste
  client_id: "yamcam"       # unique, adjust to your taste
  user: "mymqttusername"    # your mqtt username 
  password: "mymqttpassword"#         & password
  stats_interval: 30        # how often to report (via mqtt) to HA

# coupla examples of Amcrest cam rtsp feeds
cameras:
  doorfrontcam:
    ffmpeg:
      inputs:
      - path: "rtsp://user:password@x.x.x.x:554/cam/realmonitor?channel=1&subtype=1"
  frontyardcam:
    ffmpeg:
      inputs:
      - path: "rtsp://user:password@x.x.x.x:554/cam/realmonitor?channel=1&subtype=1"
```


## Notes

You'll see there is a *files* subdirectory, where I put the tflite model for yamnet,
which I downloaded from the
[TensorFlow hub](https://www.kaggle.com/models/google/yamnet/tfLite/classification-tflite/1?lite-format=tflite&tfhub-redirect=true).

You will also see *yamnet_class_map.csv* in this subdirectory. This maps the
return codes from Yamnet to the human-readable names for those classes. There are
a whopping 521 sound classes.

There is a Deprecation warning regarding the paho mqtt client and I've 
put debugging that on hold. Even with Gemini's and GPT4o's help I've been stumped
(feeding 4o the release notes and documentation, since it's training data  is only trained on
cutoff pre-dates the update to paho 2.0). On my to-do list is to try again,
perhaps with the help of Llama3... 


