#!/bin/bash

feed_cache_dir="./caches/tle-feeds"
tle_cache_dir="./caches/tle"
tmp_tle_dir="${tle_cache_dir}.tmp"

queries="
GROUP   active
GROUP   last-30-days        Launched in last 30 days
GROUP   stations            Space station
GROUP   visual              Visible
GROUP   cosmos-1408-debris  Debris from 2021 Russian anti-satellite missle test
GROUP   fengyun-1c-debris   Debris from 2007 Chinese anti-satellite missle test
GROUP   iridium-33-debris   Debris from 2009 collision with COSMOS 2251
GROUP   cosmos-2251-debris  Debris from 2009 collision with IRIDIUM 33
GROUP   analyst
GROUP   weather             Weather
GROUP   gnss                Navigation
GROUP   military            Military
GROUP   musson              Navigation
GROUP   nnss                Navigation
GROUP   noaa                Weather
GROUP   orbcomm
GROUP   satnogs
SPECIAL gpz                 GEO stationary orbit
SPECIAL gpz-plus            Graveyard orbit
SPECIAL decaying            Potential decay
"

function xit() {
    echo "$*"
    exit 1
}

RE_TRIM_RETURNS_AND_WHITESPACE='s/\s*$//'
RE_EXTRACT_SAT_NUM='^1 (.....)'

if [[ ! -d "$feed_cache_dir" ]]; then
    mkdir "$feed_cache_dir" || xit "Cannot create dir $feed_cache_dir"
fi

# File dated 24 hours ago - used to test age of previously fetched feeds.
touch --date="@$(( $(date +'%s') - 24*60*60 ))" "$feed_cache_dir/oldest-date-file"

echo "$queries" | while read query value tag
do
  [[ -z "$query" ]] && continue

  feed_file="$feed_cache_dir/${query}_${value}"
  if [[ "$feed_file" -ot "$feed_cache_dir/oldest-date-file" ]]
  then
    echo "Fetching $query=$value"
    url="https://celestrak.org/NORAD/elements/gp.php?$query=$value&FORMAT=tle"
    curl --silent --fail -o "$feed_file" "$url" || xit "Could not fetch $url"
  fi
done

echo Sorting and tagging data...
rm -rf "$tmp_tle_dir"
mkdir "$tmp_tle_dir" || xit "Cannot create dir $tmp_tle_dir"

function bracket_info() {
  if [[ "$1" == "PAM-D" ]]
  then
    echo "Payload assist module"
  elif [[ "$1" == "TANK" ]]
  then
    echo "Propellant tank"
  elif [[ "$1" == "SYLDA" || "$1" == "VESPA" || "$1" == "SPELTRA" || "$1" == "ADAPTOR" ]]
  then
    echo "Payload adaptor"
  elif [[ "$1" == "ARRAY COVER" ]]
  then
    echo "Solar array cover"
  elif [[ "$1" == "BAFFLE COVER" ]]
  then
    echo "Engine baffle cover"
  fi
}

echo "$queries" | while read query value tag
do
  [[ -z "$query" ]] && continue

  feed_file="$feed_cache_dir/${query}_${value}"
  trim_returns_and_spaces='s/\s*$//'
  sed -e "$trim_returns_and_spaces" "$feed_file" | while read name
  do
    read line1
    read line2
    
    [[ $line1 =~ ^1\ (.....) ]]
    sat_num="${BASH_REMATCH[1]}"

    base="$tmp_tle_dir/$sat_num"
    tle_file="$base.tle"
    desc_file="$base.desc"

    if [[ ! -e "$tle_file" ]]
    then
      echo "$line1" > "$tle_file"
      echo "$line2" >> "$tle_file"
      # Taking name from first record. Later feeds add clutter
      echo "$name" > "$desc_file"

      # Later we can do more with [] tags & remove tags from names.
      if [[ $name =~ \ R/B\(1\)(\ \[(.*)\])?$ ]]
      then
        echo "Stage 1 rocket body" >> "$desc_file"
        bracket_info "${BASH_REMATCH[1]}" >> "$desc_file"
      elif [[ $name =~ \ R/B\(2\)(\ \[(.*)\])?$ ]]
      then
        echo "Stage 2 rocket body" >> "$desc_file"
        bracket_info "${BASH_REMATCH[1]}" >> "$desc_file"
      elif [[ $name =~ \ R/B(\ \[(.*)\])?$ ]]
      then
        echo "Rocket body" >> "$desc_file"
        bracket_info "${BASH_REMATCH[1]}" >> "$desc_file"
      elif [[ $name =~ \ DEB(\ \[(.*)\])?$ ]]
      then
        echo "Debris" >> "$desc_file"
        bracket_info "${BASH_REMATCH[1]}" >> "$desc_file"
      fi
    fi

    # Just add tags from later feeds.
    if [[ ! -z "$tag" ]] && ! grep -qFx "$tag" "$desc_file"
    then
      echo "$tag" >> "$desc_file"
    fi
  done
done

# Move new set of tle's into position for next stage.
[[ -e "$tle_cache_dir.old/" ]] && rm -rf "$tle_cache_dir.old/"
if [[ -e "$tle_cache_dir/" ]]
then
  mv "$tle_cache_dir/" "$tle_cache_dir.old/" || xit "Cannot move existing $tle_cache_dir/ aside"
fi
mv "$tmp_tle_dir/" "$tle_cache_dir/" || xit "Cannot move $tmp_tle_dir/ to $tle_cache_dir/ aside"
[[ -e "$tle_cache_dir.old/" ]] && rm -rf "$tle_cache_dir.old/"
exit 0
