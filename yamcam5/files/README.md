## Modified YAMNet Sound Class Scheme for Convenience Integrating with Home Assistant.

This directory contains the YAMNet *tflite* model (**yamnet.tflite**)
and a **yamnet_class_map.csv**, a file that maps YAMNet output codes to
human-readable names for those classes (the *display_name*).

Because Yamnet has 521 sound classes, there are
many distinct classes that would indicate, say, music or human activity.  
Human human activity, for instance, is represented by many individual
sound classes (*giggle, hiccup, laughter, shout, sigh*, etc. as well as
*speech, crowd, or sneeze*...). Similarly, if we want to detect that
music is playing there are many many related classes (*reggae, rimshot, rock and roll,
strum, tabla*...).

The purpose for this add-on is to detect various conditions, such 
as the presence of people, playing music, inscts, or weather, sending
this information to Home Assistant via MQTT in order to:
- take some form of action via an automation, and/or
- track activities and conditions over time.
For example, one may wish to turn lights on if people are detected, or if an alarm goes off,
or to keep track the use of a space over time.

To make this easier, the classes have been grouped into categories.  In the modified
*yamnet_class_map.csv* file, the display_names have been concatenated removing spaces
and punctuation, then a group name is prepended with a "." delimeter.  For instance,
the YAMNet class "*Child speech, Kid speaking*" in the original yamnet_class_map.csv
is replaced with *people.childSpeechKidSpeaking*.

The groupings are also skewed toward outdoor sounds, though YAMNet
has many classes for sounds like cooking or doors closing or other indoor 
sounds.  These are grouped as "domestic" which is *sort of* people activy,
but are kept separate from the *people* group. 

The original *yamnet_class_map* is preserved here as **yamnet_class_map_ORIG.csv**.
It is straightforward to re-group
(i.e., rename) classes in the *yamnet_class_map.csv* file, but *you must keep 
the file sorted in index order as the scores are returned in that order.*

The tflite model *yamnet.tflite* and *yamnet_class_map.csv* were downloaded from 
[TensorFlow hub](https://www.kaggle.com/models/google/yamnet/tfLite/classification-tflite/1?lite-format=tflite&tfhub-redirect=true).
