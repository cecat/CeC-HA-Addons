
# Changelog

## 1.0.0
- Eliminated the *exclude_groups* list as we have a *sounds*->*track* list already,
  so any group not in that list will be excluded (previously all groups/classes were
  logged irrespective of the *track* list).
- Stopped logging classes from excluded groups. Mostly because the CSV was primarily "silence" which
  meant huge files and (more importantly) a vast majority of rows being silence (not useful).

## Previous Version Changelog
- Preserved at 
