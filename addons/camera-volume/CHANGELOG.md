# Changelog

## 1.0.d
- Fix python coding error

## 1.0.c
- Changed yaml structure of /config/cameravolume.yaml to be more yaml-compliant w.r.t. key nesting
- Modified get_audio_volume.py to read new (more compliant) YAML structure
- Updated README.md example for /config/cemaravolume.yaml (and updated the example)

## 1.0.b
- Added detail about camervolume.yaml in README
- Fixed a warning issue re formatting in config.yaml

## 1.0.a
- Fixed formatting issue in README

## 1.0.9
- Add some helpful comments to the python script and README

## 1.0.8
- Revert to version 1.0.4 of the code, live to fight the warning another day.

## 1.0.7
- Another attempt to fix the pesky mqtt version warning

## 1.0.6
- (fixed typo in) attempt to address Deprecation Warning related to mqtt Callback API 

## 1.0.5
- attempt to address Deprecation Warning related to mqtt Callback API 

## 1.0.4
- change the log messages to send the volume values rounded to 2 decimal places

## 1.0.3
- change the mqtt publish to send the volume values rounded to 2 decimal places

## 1.0.2
- fix sampling interval - was 5s duration every 5s (i.e., continuous) - now 5s duration every 10s.

## 1.0.1
- basic running add-on
