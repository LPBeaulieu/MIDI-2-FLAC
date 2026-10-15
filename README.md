# Midi2Flac
Midi2Flac lets you render MIDI files as FLAC audio files with SF2 soundfont files, complete with metadata information

<h3 align="center">Midi2Flac</h3>
<div align="center">
  
  [![License: AGPL-3.0](https://img.shields.io/badge/License-AGPLv3.0-brightgreen.svg)](https://github.com/LPBeaulieu/MIDI-2-FLAC/blob/main/LICENSE)
  ![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
  ![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
  
</div>

---

<p align="left"> Be sure to also check out my other repo <b>MusicReader</b>, which is an application that generates MIDI files from scanned music box scoresheet JPEG files, complete with features such as tempo adjustment, transposition, and addition of silence to the start and end of the MIDI files, essentially turning your music box into an analog version of a Digital Audio Workstation (DAW)! Here's a link to the repo: https://github.com/LPBeaulieu/MusicReader.
</p>

## 📝 Table of Contents
- [Getting Started](#getting_started)
- [Usage](#usage)
- [Author](#author)
- [Acknowledgments](#acknowledgments)

## 🏁 Getting Started <a name = "getting_started"></a>

The following instructions will be provided in great detail, as they are intended for a broad audience and will
allow to run a copy of <b>Midi2Flac</b> on a local computer. 

<b>Step 1</b>- Create a virtual environment (called <i>env</i>, or any other name of your choosing) in your working folder:
```
python3 -m venv env
```

<b>Step 2</b>- Activate the <i>env</i> virtual environment <b>(you will need to do this step every time you use the Python code files)</b> 
in your working folder:

For Windows
```
env/Scripts/activate 
```
For Linux:
```
source env/bin/activate
```

<b>Step 3</b>- Install <b>mutagen</b> (Python library for audio file metadata handling)
```
pip install mutagen
```

<b>Step 4</b>- Include the <b>FluidSynth</b> library in your working folder (Library for rendering MIDI files):
- **Midi2Flac** relies on the FluidSynth library (included in the zipped release folder) to render the MIDI files to FLAC files. As such, **the FluidSynth binary folder is required in the working folder**. As of October 2026, only the FluidSynth versions up to 2.3.0 allow to reliably render MIDI files without appending extra silence to the end of the rendered audio files (see Issue #1408 of the FluidSynth GitHub for more details). You should then select one of these versions from the following link if FluidSynth is not already found in your working folder: https://github.com/FluidSynth/fluidsynth/releases.

<b>Step 5</b>- Create the "Album Cover Image" and "MIDI Files" subfolders within your working folder:
```
mkdir "Album Cover Image", "MIDI Files" 
```
<b>Step 6</b>- Add at least one MIDI file to the "MIDI Files" folder and include your album cover PNG or JPEG image in the "Album Cover Image" folder. Fill out any relevant metadata information in the second column (B) of the "metadata_csv_file.csv" comma-separated value (CSV) file within the "Metadata CSV File" subfolder, such as the album name, release year (more info on that below). You may also want to swap out the SF2 files included in the "SF2 Files".
  
<b>Step 7</b>- You're now ready to use <b>Midi2Flac</b>! 🎉

## 🎈 Usage <a name="usage"></a>
Here are a few important pointers for best results:

**Midi2Flac** relies on the FluidSynth library (included in the zipped release folder) to render the MIDI files to FLAC files.

As such, **the FluidSynth binary folder is required in the working folder**. As of October 2026, only the FluidSynth versions up to 2.3.0 allow to reliably render MIDI files without appending extra silence to the end of the rendered audio files (see Issue #1408 of the FluidSynth GitHub for more details). You should then select one of these versions from the following link if FluidSynth is not already found in your working folder: https://github.com/FluidSynth/fluidsynth/releases.

**Midi2Flac** also relies on the **mutagen** Python library for **adding Vorbis comment metadata** information to the FLAC files. You may install it as follows if you are running the Midi2Flac Python script instead of the executable application:
```
py -m pip install mutagen
```

You will need to include **at least one MIDI file in the "MIDI Files" folder and at least one SF2 file in the "SF2 Files"** folder in order for the code to be able to render the MIDI files using the SF2 soundfont files. A FLAC file will be generated with each of the SF2 files, for each of the MIDI files. That is to say, should you have two different SF2 files and three different MIDI files, you would then end up with six different FLAC files (one set generated with each soundfont file), with the FLAC file names suffixed with the soundfont they were created with. For example, when rendering with the "piano.sf2" and "guitar.sf2" soundfont files the following FLAC files will be generated: "1 - Song one (piano).flac", "1 - Song one (guitar).flac", "2 - Song two (piano).flac", "2 - Song two (guitar).flac", etc.

The default gain of FluidSynth is 0.2, with possible values spanning 0.0 to 10.0, inclusively, and larger values resulting in louder output. **The gain needs to be specified in the file names of the SF2 files**, separated by a hyphen, and must 
always be written in floating point format (e.g., "piano - 1.0.sf2"). Any gain values present in the SF2 file names will not end up in the FLAC file names, as they will be truncated by the code (see paragraph above).

Here is a description of how to provide Midi2Flac with the required metadata information:

- The **MIDI file names**, after the code removes the ".mid" extensions, will automatically be used to provide the value for the **"title"** metadata tags.

- Any **track numbering prefixes** will be extracted by the code for use in the "tracknumber" metadata tags (e.g., track number 1 will be extracted from "1-my_song.mid").

- You may **add a JPEG or PNG image to the "Album Cover Image" subfolder** of the working folder, and the image will automatically be downsized to a file size of 500 KB and thumbnailed if its largest side dimension exceeds the threshold of 800 pixels. You may provide your own values for these thresholds by passing in your settings of choice after the colons in the **"target_image_size:"** (e.g., "target_image_size:200" for 200 KB) and **"target_image_dimension:"** (e.g., "target_image_dimension:500" for 500 pixels) arguments.

When running the application with additional arguments, open a PowerShell window in the root folder and enter the following (while adjusting the values to your preferred settings, making sure to place the arguments within quotes and separating each argument with a space):
```
./midi2flac.exe "target_image_size:200" "target_image_dimension:500"
```
When running the Python script instead of the executable file, you would enter this command:
```
python midi2flac.py "target_image_size:200" "target_image_dimension:500"
```

- The **image description text** will correspond to the **image's file name**, excluding the ".jpg" or ".png" extension, unless you pass in your image's description text after the colon in the **"image_description:"** argument. 

- The **sample rate** of the generated FLAC files (default 44100 Hz) can be set to another value by providing it after the colon in the **"sample_rate:"** argument when running the code. Values between 8000 and 96000 are accepted.

- A **comma-separated value (CSV) file with tab delimiters** is automatically generated by the code in the "Metadata CSV File" subfolder of the working folder. It contains the "album", "artist", "comment", "copyright", "genre", "language", "totaltracks" (indicating the total amount of tracks present on your album), "website", and "year". Simply open the CSV file in a spreadsheet and **add your metadata values to the second column (B)**, beside each metadata tag found in column (A), as in the following example. Please note that leaving any fields empty (as in the "language" tag that doesn't apply to instrumental music) will result in the exclusion of these metadata tags from your FLAC files:

  - **album**: Bach Music Box
  - **artist**: J. S. Bach
  - **comment**: Arranged for a 30-note music box.
  - **copyright**: CC BY SA 4.0
  - **genre**: classical
  - **language**:	
  - **totaltracks**: 20
  - **website**: www.example.com
  - **year**: 2026

You may also **add some more tags to the CSV file** by adding the tags starting from the first empty cell of column (A), and their values in the corresponding rows in column (B). For more metadata tags, please consult the following link:
https://picard-docs.musicbrainz.org/en/latest/variables/tags_basic.html

The FLAC files will be generated in the "Generated FLAC Files" subfolder of the working folder.
        
<br><b>And that's it!</b> Happy rendering! 🎉📖
  
  
## ✍️ Authors <a name = "author"></a>
- 👋 Hi, I’m Louis-Philippe!
- 👀 I’m interested in natural language processing (NLP) and anything to do with words, really! 📝
- 🌱 I’m currently reading about deep learning (and reviewing the underlying math involved in coding such applications 🧮😕)
- 📫 How to reach me: By e-mail! LPBeaulieu@gmail.com 💻


## 🎉 Acknowledgments <a name = "acknowledgments"></a>
- Hat tip to [@kylelobo](https://github.com/kylelobo) for the GitHub README template!
