# Camera-sounds add-on for Home Assistant
CeC
July 2024

---


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
Be patient the first time you install...  It builds a pretty complicated
image so the first time
installation will take 5-10 minutes depending on the speed of your Internet
connection and of your CPU (it took 13 minutes to build on an RPi-4).
Subsequent updates will not take nearly so long. (I will try to improve this...
right now just going for functionality))

## Configuring this Add-on

The code right now has very extensive logging as I am experimenting with things like
sample frequency and thresholds.  For each sound source, at each reporting interval,
we send a MQTT  message to HA of the form "Class (score), Class (score)..."

0. This addon assumes you are running a MQTT broker already. This code
has (only) been tested with the open source
[Mosquitto broker](https://github.com/home-assistant/addons/tree/master/mosquitto) 
from the *Official add-ons* repository.

1. Create a file, *microphones.yaml* with specifics regarding your MQTT broker address,
MQTT username and password, and RTSP feeds. These will be the same feeds you use
in Frigate (if you use Frigate), which may have embedded credentials
(so treat this as a secrets file). If you want to report less frequently than
every 60s you can change the *stats_interval* value in this file.  This configuration
file will look something like below. Put this file into */config*.

```
general:
  sample_interval: 15       # Sampling frequency (seconds)
  reporting_threshold: 0.4  # Reporting threshold for sound type scores

mqtt:
  host: "x.x.x.x"
  port: 1883
  topic_prefix: "HA/sensor"
  client_id: "yamcam"
  user: "mymqttusernameforcamvol"
  password: "mymqttpasswordforcamvol"
  stats_interval: 30
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

There is a Deprecation warning regarding the paho mqtt client and I've given up
trying to address that for now, as even with GPT4o's help I could not fix it.


