#!/bin/bash

feed_cache_dir="./caches/tle-feeds"
tle_cache_dir="./caches/tle"
tmp_tle_dir="${tle_cache_dir}.tmp"

GPZ_TAG="Geo protected zone"
GPZ_PLUS_TAG="Geo protected plus"

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
SPECIAL gpz                 $GPZ_TAG
SPECIAL gpz-plus            $GPZ_PLUS_TAG
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

# Fetch files no more that one in 24 hours to avoid getting blocked:
# https://celestrak.org/NORAD/documentation/gp-data-formats.php#addendum
# File dated 24 hours ago - used to test age of previously fetched feeds.
touch --date="@$(( $(date +'%s') - 24*60*60 ))" "$feed_cache_dir/oldest-date-file"

echo "$queries" | while read query value tag
do
  [[ -z "$query" ]] && continue

  gp_feed_file="$feed_cache_dir/${query}_${value}"
  if [[ "$gp_feed_file" -ot "$feed_cache_dir/oldest-date-file" ]]
  then
    echo "Fetching TLE    $query=$value"
    url="https://celestrak.org/NORAD/elements/gp.php?$query=$value&FORMAT=tle"
    curl --silent --fail -o "$gp_feed_file" "$url" || xit "Could not fetch $url"
  fi

  if [[ ! ( "${query}" = "SPECIAL" && "${value}" = "decaying" ) &&
        ! ( "${query}" = "GROUP"   && "${value}" = "analyst"  ) ]]
  then
    satcat_feed_file="$feed_cache_dir/${query}_${value}.cat"
    if [[ "$satcat_feed_file" -ot "$feed_cache_dir/oldest-date-file" ]]
    then
      echo "Fetching SATCAT $query=$value"
      url="https://celestrak.org/satcat/records.php?$query=$value&FORMAT=csv"
      curl --silent --fail -o "$satcat_feed_file" "$url" || xit "Could not fetch $url"
    fi
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

NL=$'\n                       '
declare -A owners=(
    [AB]="Arab Satellite Communications${NL}Organization"
    [ABS]="Asia Broadcast Satellite"
    [AC]="Asia Satellite Telecommunications${NL}Company (ASIASAT)"
    [ALG]="Algeria"
    [ANG]="Angola"
    [ARGN]="Argentina"
    [ARM]="Republic of Armenia"
    [ASRA]="Austria"
    [AUS]="Australia"
    [AZER]="Azerbaijan"
    [BEL]="Belgium"
    [BELA]="Belarus"
    [BERM]="Bermuda"
    [BGD]="Peoples Republic of Bangladesh"
    [BHR]="The Kingdom of Bahrain"
    [BHUT]="The Kingdom of Bhutan"
    [BOL]="Bolivia"
    [BRAZ]="Brazil"
    [BUL]="Bulgaria"
    [BWA]="Republic of Botswana"
    [CA]="Canada"
    [CHBZ]="China/Brazil"
    [CHTU]="China/Türkiye"
    [CHLE]="Chile"
    [CIS]="Commonwealth of Independent${NL}States (former USSR)"
    [COL]="Colombia"
    [CRI]="Republic of Costa Rica"
    [CZCH]="Czech Republic${NL}(former Czechoslovakia)"
    [DEN]="Denmark"
    [DJI]="Republic of Djibouti"
    [ECU]="Ecuador"
    [EGYP]="Egypt"
    [ESA]="European Space Agency"
    [ESRO]="European Space Research${NL}Organization"
    [EST]="Estonia"
    [ETH]="Ethiopia"
    [EUME]="European Organization for the${NL}Exploitation of Meteorological${NL}Satellites (EUMETSAT)"
    [EUTE]="European Telecommunications${NL}Satellite Organization (EUTELSAT)"
    [FGER]="France/Germany"
    [FIN]="Finland"
    [FR]="France"
    [FRIT]="France/Italy"
    [GER]="Germany"
    [GHA]="Republic of Ghana"
    [GLOB]="Globalstar"
    [GREC]="Greece"
    [GRSA]="Greece/Saudi Arabia"
    [GUAT]="Guatemala"
    [HRV]="Republic of Croatia"
    [HUN]="Hungary"
    [IM]="International Mobile Satellite${NL}Organization (INMARSAT)"
    [IND]="India"
    [INDO]="Indonesia"
    [IRAN]="Iran"
    [IRAQ]="Iraq"
    [IRID]="Iridium"
    [IRL]="Ireland"
    [ISRA]="Israel"
    [ISRO]="Indian Space Research Organisation"
    [ISS]="International Space Station"
    [IT]="Italy"
    [ITSO]="International Telecommunications${NL}Satellite Organization${NL}(INTELSAT)"
    [JPN]="Japan"
    [KAZ]="Kazakhstan"
    [KEN]="Republic of Kenya"
    [LAOS]="Laos"
    [LKA]="Democratic Socialist Republic of${NL}Sri Lanka"
    [LTU]="Lithuania"
    [LUXE]="Luxembourg"
    [MA]="Morroco"
    [MALA]="Malaysia"
    [MCO]="Principality of Monaco"
    [MDA]="Republic of Moldova"
    [MEX]="Mexico"
    [MMR]="Republic of the Union of Myanmar"
    [MNE]="Montenegro"
    [MNG]="Mongolia"
    [MUS]="Mauritius"
    [NATO]="North Atlantic Treaty${NL}Organization"
    [NETH]="Netherlands"
    [NICO]="New ICO"
    [NIG]="Nigeria"
    [NKOR]="Democratic People's${NL}Republic of Korea"
    [NOR]="Norway"
    [NPL]="Federal Democratic${NL}Republic of Nepal"
    [NZ]="New Zealand"
    [O3B]="O3b Networks"
    [ORB]="ORBCOMM"
    [PAKI]="Pakistan"
    [PERU]="Peru"
    [POL]="Poland"
    [POR]="Portugal"
    [PRC]="People's Republic of China"
    [PRY]="Republic of Paraguay"
    [PRES]="People's Republic of China/${NL}European Space Agency"
    [QAT]="State of Qatar"
    [RASC]="RascomStar-QAF"
    [ROC]="Taiwan (Republic of China)"
    [ROM]="Romania"
    [RP]="Philippines (Republic of${NL}the Philippines)"
    [RWA]="Republic of Rwanda"
    [SAFR]="South Africa"
    [SAUD]="Saudi Arabia"
    [SDN]="Republic of Sudan"
    [SEAL]="Sea Launch"
    [SEN]="Republic of Senegal"
    [SES]="SES"
    [SGJP]="Singapore/Japan"
    [SING]="Singapore"
    [SKOR]="Republic of Korea"
    [SLB]="Solomon Islands"
    [SPN]="Spain"
    [STCT]="Singapore/Taiwan"
    [SVN]="Slovenia"
    [SWED]="Sweden"
    [SWTZ]="Switzerland"
    [TBD]="To Be Determined"
    [THAI]="Thailand"
    [TMMC]="Turkmenistan/Monaco"
    [TUN]="Republic of Tunisia"
    [TURK]="Türkiye"
    [UAE]="United Arab Emirates"
    [UK]="United Kingdom"
    [UKR]="Ukraine"
    [UNK]="Unknown"
    [URY]="Uruguay"
    [US]="United States"
    [USBZ]="United States/Brazil"
    [VAT]="Vatican City State"
    [VENZ]="Venezuela"
    [VTNM]="Vietnam"
    [ZWE]="Republic of Zimbabwe"
)

declare -A sites=(
    [AFETR]="Air Force Eastern Test Range,${NL}Florida, USA"
    [AFWTR]="Air Force Western Test Range,${NL}California, USA"
    [ANDSP]="Andøya Spaceport, Nordland,${NL}Norway"
    [ALCLC]="Alâcantara Launch Center,${NL}Maranhão, Brazil"
    [BOS]="Bowen Orbital Spaceport,${NL}Queensland, Australia"
    [CAS]="Canaries Airspace"
    [DLS]="Dombarovskiy Launch Site,${NL}Russia"
    [ERAS]="Eastern Range Airspace"
    [FRGUI]="Europe's Spaceport, Kourou,${NL}French Guiana"
    [HGSTR]="Hammaguira Space Track Range,${NL}Algeria"
    [JJSLA]="Jeju Island Sea Launch Area,${NL}Republic of Korea"
    [JSC]="Jiuquan Space Center, PRC"
    [KODAK]="Kodiak Launch Complex, Alaska,${NL}USA"
    [KSCUT]="Uchinoura Space Center Fomerly${NL}Kagoshima Space Center,${NL}Japan"
    [KWAJ]="US Army Kwajalein Atoll (USAKA)"
    [KYMSC]="Kapustin Yar Missile and${NL}Space Complex, Russia"
    [NSC]="Naro Space Complex, Republic of${NL}Korea"
    [PLMSC]="Plesetsk Missile and Space${NL}Complex, Russia"
    [RLLB]="Rocket Lab Launch Base, Mahia${NL}Peninsula, New Zealand"
    [SCSLA]="South China Sea Launch Area, PRC"
    [SEAL]="Sea Launch Platform (mobile)"
    [SEMLS]="Semnan Satellite Launch Site,${NL}Iran"
    [SMTS]="Shahrud Missile Test Site, Iran"
    [SNMLP]="San Marco Launch Platform,${NL}Indian Ocean (Kenya)"
    [SPKII]="Space Port Kii, Japan"
    [SRILR]="Satish Dhawan Space Centre,${NL}India (Formerly Sriharikota Launching Range)"
    [SUBL]="Submarine Launch Platform (mobile)"
    [SVOBO]="Svobodnyy Launch Complex, Russia"
    [TAISC]="Taiyuan Space Center, PRC"
    [TANSC]="Tanegashima Space Center, Japan"
    [TYMSC]="Tyuratam Missile and Space${NL}Center, Kazakhstan"
    [UNK]="Unknown"
    [VOSTO]="Vostochny Cosmodrome, Russia"
    [WLPIS]="Wallops Island, Virginia, USA"
    [WOMRA]="Woomera, Australia"
    [WRAS]="Western Range Airspace"
    [WSC]="Wenchang Satellite Launch Site,${NL}PRC"
    [XICLF]="Xichang Launch Facility, PRC"
    [YAVNE]="Yavne Launch Facility, Israel"
    [YSLA]="Yellow Sea Launch Area, PRC"
    [YUN]="Yunsong Launch Site, Democratic${NL}People's Republic of Korea${NL}(North Korea)"
)

echo "$queries" | while read query value tag
do
  [[ -z "$query" ]] && continue

  gp_feed_file="$feed_cache_dir/${query}_${value}"

  declare -A feed_owners
  declare -A feed_ldates
  declare -A feed_sites
  if [[ -e "$gp_feed_file.cat" ]]
  then
    while IFS=, read -ra satcat; do
      sat_num="${satcat[2]}"
      owner_code="${satcat[5]}"
      feed_owners[$sat_num]="${owners[$owner_code]}"
      launch_date="${satcat[6]}"
      feed_ldates[$sat_num]="$launch_date"
      site_code="${satcat[7]}"
      feed_sites[$sat_num]="${sites[$site_code]}"
    done < "$gp_feed_file.cat"
  fi

  trim_returns_and_spaces='s/\s*$//'
  sed -e "$trim_returns_and_spaces" "$gp_feed_file" | while read name
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
      # Taking details from record in first feed. Later ones only add clutter
      echo "$name" > "$desc_file"

      if [[ -v feed_owners[$sat_num] ]]
      then
        echo "Ownership:   ${feed_owners[$sat_num]}" >> "$desc_file"
      fi
      if [[ -v feed_ldates[$sat_num] ]]
      then
        echo "Launch date: ${feed_ldates[$sat_num]}" >> "$desc_file"
      fi
      if [[ -v feed_sites[$sat_num] ]]
      then
        echo "Launch site:   ${feed_sites[$sat_num]}" >> "$desc_file"
      fi
      echo "" >> "$desc_file"

      # Later we could do more with [] tags in names.
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
      elif [[ $name =~ \ DEB(\ \[(.*)\])?$ && \
              $value != cosmos-1408-debris && \
              $value != fengyun-1c-debris && \
              $value != iridium-33-debris && \
              $value != cosmos-2251-debris ]]
      then
        echo "Debris" >> "$desc_file"
        bracket_info "${BASH_REMATCH[1]}" >> "$desc_file"
      fi
    fi

    # Don't re-add duplicate tags
    if [[ ! -z "$tag" ]] && ! grep -qFx "$tag" "$desc_file"
    then
      # Also don't add the gpz-plus tag if the gpz tag is already there.
      if [[ "$tag" != "$GPZ_PLUS_TAG" ]] || ! grep -qFx "$GPZ_TAG" "$desc_file"
      then
        echo "$tag" >> "$desc_file"
      fi
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
