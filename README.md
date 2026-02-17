# tal-drum-from-name-preset-generator
generator of preset of tal drum from named wav files



This python code generates code from folder of wav files using the following format
`<drum type > <drum kit name> <number>.wav ` (ex : 'kick dubstep 1.wav' 'snare boombap 1.wav', etc)

it uses 2 scripts : 
 - create_listing.py : generate listing of samples ordered by  kits in json format. 

    example : 

    ```json


    {
    "808X": {
        "clap": [
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Clap/Clap 808X.wav"
        ],
        "crash": [
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Cymbal/Crash 808X.wav"
        ],
        "kick": [
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Kick/Kick 808X 1.wav",
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Kick/Kick 808X 2.wav",
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Kick/Kick 808X 3.wav",
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Kick/Kick 808X 4.wav"
        ],
        "shaker": [
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Shaker/Shaker 808X.wav"
        ],
        "snare": [
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Snare/Snare 808X 1.wav",
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Snare/Snare 808X 2.wav"
        ]
    },
    "AwakeArise": {
        "clap": [
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Clap/Clap AwakeArise 1.wav",
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Clap/Clap AwakeArise 2.wav"
        ],
        "crash": [
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Cymbal/Crash AwakeArise.wav"
        ],
        "kick": [
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Kick/Kick AwakeArise 1.wav",
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Kick/Kick AwakeArise 2.wav"
        ],
        "shaker": [
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Shaker/Shaker AwakeArise.wav"
        ],
        "snare": [
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Snare/Snare AwakeArise 1.wav",
        "/media/baldwin/T7 Shield/MAO/02-resources/samples/packs/MaschineFactorySamples/Drums/Snare/Snare AwakeArise 2.wav"
        ]
    }
    }
    ```

 - generate.py : generate .taldrum presets from listing file (one for each kit). Please note that when multiple samples of one category are found for one instrument (example 12 differents kicks for a given kit), presets are generated as velocity layer in the same pad.


 ## usage




 ### create_listing.py

 ```
positional arguments:
  samples_folder

options:
  -h, --help            show this help message and exit
  --mapping MAPPING
  --min-total MIN_TOTAL
  --exclude-only-other
  --exclude-mixed-other
  --overflow-policy {reject,truncate,trash,ignore}
  --trash-notes TRASH_NOTES
                        MIDI trash notes (e.g. 82-127). Default: 82-127
  --export-valid EXPORT_VALID
  --export-rejected EXPORT_REJECTED
 ```

 - ```samples_folder``` : path root containing the wav file to analyse. Folder structure can be complex as analysis is recursive
 - ```--mapping``` : file containing the rules to create the mapping. Ex: 
    ``` 
    kick/bass drum : 36
    SideStick/rim : 37
    snare/snr : 38, 40 
    hihat/hh/closedhh/pedalhh : 42
    pedalhh : 44
    Oh/openhh : 46
    clap/Snap : 39
    Tom : 42, 50  
    shaker : 58
    combo : 30, 31
    crash/china/splash/ridebell/ride/cymbal/revCrash : 49, 57
    bell : 53
    ```
    In this example, 'kick' and 'bass drum' are considered synonyms during parsing, and are destined to be mapped on a pad with midi note 36. 'Combo' can be mapped both on note 30 and 31 (1 pad = 8 samples max, 2 pads = 16 samples and so on)
 - ```--min-total``` : filter out kits with less than ```--min-total``` samples.
 - ```--exclude-only-other``` : exclude kits where all samples didn't fall in any category (ex: "violin boombap 1.wav ")
 - ```--exclude-mixed-other``` : exlclude kits where anay samples samples didn't fall in any category
 - ```--overflow-policy``` : policy to handle files of uncategorized samples or when too many sample of a given category are found (each pad can only have 8 velocity layers). 
 - ```--trash-notes``` :  range of midi notes used to store samples when "trash" overflow policy is used. 
 - ```--export-valid``` : output json file for valid kits
 - ```--export-rejected``` : output json file for invalid kits  


### generate.py

```
positional arguments:
  listing_json

options:
  -h, --help            show this help message and exit
  --mapping MAPPING
  --output-dir OUTPUT_DIR
  --global-sample-base GLOBAL_SAMPLE_BASE
  --overflow-policy {reject,truncate,trash,ignore}
  --trash-notes TRASH_NOTES
  --pad-base-midi PAD_BASE_MIDI
  --pad-count PAD_COUNT
```

- ```listing_json``` : json file of kits to generate 
- ```--mapping``` : mapping file, same than for create_listing.py
- ```--output-dir``` : output directory to store the tal drum presets
- ```--global-sample-base``` : "global sample path" (optionnal). Should be the same as the one provided to tal drum global settings
- ``` --overflow-policy```  : same as before 
- ```--pad-base-midi``` : midi note of first midi pad
-  ```--pad-count PAD_COUNT``` : number of pads in taldrum (64)
