import csv
from datetime import datetime
import io
import mutagen
from mutagen.flac import Picture
import os
from PIL import Image
import re
import shutil
import signal
import subprocess
import sys
import textwrap
import time
import traceback


#The "clear_screen()" function will clear the CLI screen
#using the appropriate command depending on the operating system.
def clear_screen():
    #'nt' is for Windows, 'posix is for Linux/Raspberry Pi/macOS (else statement)
    os.system('cls' if os.name == 'nt' else 'clear')

#The Signal Interrupt (SIGINT) handler will
#call the "signal_interrupt_signal_handler()" function 
#when the user presses on CTRL + C to exit the app.

#The function "signal_interrupt_signal_handler()" will call
#"sys.exit(0)" to exit the program normally.
def signal_interrupt_signal_handler(sig, frame):
    sys.exit(0)

#The function "write_entry_in_error_log()" will write 
#the full technical traceback error to the error log.
def write_entry_in_error_log():
    with open("ERROR LOG.txt", "a", encoding="utf-8") as error_log:
        error_log.write(f"\n--- Error at {datetime.now()} ---\n")
        traceback.print_exc(file=error_log)

#The function "display_progress()" will display the progress string in the console
#and return the estimated number of seconds for the code to complete.
def display_progress(current_midi_index, first_midi_index, last_midi_index, start_time, previous_estimated_seconds):
            
    elapsed_seconds = time.perf_counter() - start_time
    #divmod returns (minutes, remaining_seconds)
    mins, secs = divmod(round(elapsed_seconds), 60)
    time_string = f"{mins:02}:{secs:02}"
    eta_string = ""

    #If the MIDI file will only be comprised of one scoresheet 
    #scan, then the "percent_completion" will be 100% after 
    #processing that MIDI file (so as to avoid "Division 
    #by Zero" errors).
    if last_midi_index - first_midi_index == 0:
        percent_completion = 100
        eta_string = f" ETA: 00:00\n"
    else:
        #The percent completion is calculated by dividing the one-indexed current MIDI index (hence the "+1")
        #by the total number of MIDI files to be processed, equals the value of "last_midi_index" plus one.
        #The resulting quotient is multiplied by 100 and then rounded when printed on-screen.
        percent_completion = (current_midi_index+1)/(last_midi_index+1) * 100

    #The previous estimation of the remaining number of seconds is stored in the variable
    #"previous_estimated_seconds" and will be used instead of the current calculation
    #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
    #its estimation.
    estimated_seconds = previous_estimated_seconds
    #A delay of 3 MIDI files is used to be able to gather a somewhat accurate value
    #of the elapsed time for a given percent completion value.
    if (last_midi_index > first_midi_index + 3 and current_midi_index > first_midi_index + 3):
        #The estimated number of seconds left is calculated by doing the cross-multiplication between
        #the number of percentage points left to reach completion ("100 - percent_completion") 
        #and the elapsed time for the current percent completion.
        estimated_seconds = round((100 - percent_completion) * elapsed_seconds / percent_completion)
        #The previous estimation of the remaining number of seconds is stored in the variable
        #"previous_estimated_seconds" and will be used instead of the current calculation
        #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
        #its estimation.
        if (previous_estimated_seconds != 0 and estimated_seconds > previous_estimated_seconds):
            estimated_seconds = previous_estimated_seconds

        #If the current MIDI index is the last MIDI index,
        #then the remaining time is zero seconds (" ETA: 00:00").
        if (current_midi_index == last_midi_index):
            percent_completion = 100
            eta_string = f" ETA: 00:00\n"
        #We do not want to display negative times, hence the
        #condition ("elif (estimated_seconds > 0)").
        elif (estimated_seconds > 0):
            eta_mins, eta_secs = divmod(round(estimated_seconds), 60)
            eta_string = f" ETA: {eta_mins:02}:{eta_secs:02}"

    #"\r" resets the line
    sys.stdout.write(f"\rRendered MIDI file: {current_midi_index+1} of {last_midi_index+1} ({round(percent_completion)}%) Time: {time_string}{eta_string}")

    return estimated_seconds

#The function "get_terminal_dimensions()" will return the number of columns 
#and rows in the console, to allow to properly format the text and dividers.
def get_terminal_dimensions():
    #Detect columns (width) and lines (height)
    #Returns a named tuple; default fallback is (80, 24)
    size = shutil.get_terminal_size(fallback=(80, 24))
    return int(size.columns * 0.75), int(size.lines)
    
     
if __name__ == '__main__':
    
    #The "clear_screen()" function will clear the CLI screen
    #using the appropriate command depending on the operating system.
    clear_screen()
    
    metadata_csv_folder_name = "Metadata CSV File"
    album_cover_image_folder_name = "Album Cover Image"
    sf2_folder_name = "SF2 Files"
    midi_folder_name = "MIDI Files"
    output_flac_folder_name = "Generated FLAC Files"
    press_any_key_string = "Press any key to continue." 
    sample_rate = "44100"
    #The default gain of FluidSynth is 0.2, with 
    #possible values spanning 0.0 to 10.0, inclusively,
    #and larger values resulting in louder output.
    #The gain needs to be specified in the file names 
    #of the SF2 files, separated by a hyphen, and must 
    #always be written in floating point format
    #(e.g., "piano - 1.0.sf2").
    default_gain_value = "0.2"
    debug_mode = False
    cover_image_description = ""
    img_size_kilobyte_threshold = 500
    img_dimension_pixel_threshold = 800
    metadata_dict = {}
    #The Boolean variable "has_user_passed_in_image_description_argument",
    #initialized to "False" will be set to "True" should the user have 
    #passed in a cover image description after the "image_description:"
    #argument when running the code. This Boolean variable, when set 
    #to "True" will prevent the code from extracting the cover image 
    #description text form the PNG or JPEG image file name.
    has_user_passed_in_image_description_argument = False
    
    #The function "get_terminal_dimensions()" will return the number of columns 
    #and rows in the console, to allow to properly format the text and dividers.
    columns, lines = get_terminal_dimensions()
    
    if len(sys.argv) > 1:
        #The "try/except" statement will
        #intercept any "ValueErrors" and
        #ask the users to correctly enter
        #the desired values for the variables
        #directly after the colon separating
        #the variable name from the value.
        try:  
            for i in range(1, len(sys.argv)):
                argv_strip_lower = sys.argv[i].strip().lower()
                if argv_strip_lower[:12] == "sample_rate:":
                    sample_rate = argv_strip_lower[12:].strip()
                elif argv_strip_lower[:18] == "target_image_size:":
                    img_size_kilobyte_threshold = int(argv_strip_lower[18:].strip())    
                elif argv_strip_lower[:23] == "target_image_dimension:":
                    img_dimension_pixel_threshold = int(argv_strip_lower[23:].strip())
                elif argv_strip_lower[:18] == "image_description:":
                    #"sys.argv[i].strip()" is used instead of "argv_strip_lower",
                    #as we want to preserve the case information in the original string.
                    cover_image_description = sys.argv[i].strip()[18:].strip()
                    #The Boolean variable "has_user_passed_in_image_description_argument",
                    #initialized to "False" will be set to "True" should the user have 
                    #passed in a cover image description after the "image_description:"
                    #argument when running the code. This Boolean variable, when set 
                    #to "True" will prevent the code from extracting the cover image 
                    #description text form the PNG or JPEG image file name.
                    has_user_passed_in_image_description_argument = True
                elif argv_strip_lower[:10] == "debug_mode":
                    debug_mode = True
                    
        except Exception as e:
            print(e)
            
            print("\n" + textwrap.fill('Please enter the name of the parameter you wish to alter, followed ' +
            'by a colon, and the desired setting directly after the colon. For example, ' +
            'to set the target cover image size to 200 KB, you would enter: "target_image_size:200".', columns) + "\n")
            input(press_any_key_string)
            sys.exit(1)
    
    README_STRING = """======================
README FOR MIDI-2-FLAC
======================

The **Midi2Flac** application will **render MIDI files as FLAC files using SF2 soundfont files**. It will then add Vorbis comment metadata information to the generated FLAC files.

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

album		Bach Music Box
artist		J. S. Bach
comment		Arranged for a 30-note music box.
copyright	CC BY SA 4.0
genre		classical
language	
totaltracks	20
website		www.example.com
year		2026

You may also **add some more tags to the CSV file** by adding the tags starting from the first empty cell of column (A), and their values in the corresponding rows in column (B). For more metadata tags, please consult the following link:
https://picard-docs.musicbrainz.org/en/latest/variables/tags_basic.html

The FLAC files will be generated in the "Generated FLAC Files" subfolder of the working folder.

Happy Rendering!"""

    LICENSE_STRING = """Copyright (c) 2026 The Midi2Flac Author

GNU AFFERO GENERAL PUBLIC LICENSE
                       Version 3, 19 November 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The GNU Affero General Public License is a free, copyleft license for
software and other kinds of works, specifically designed to ensure
cooperation with the community in the case of network server software.

  The licenses for most software and other practical works are designed
to take away your freedom to share and change the works.  By contrast,
our General Public Licenses are intended to guarantee your freedom to
share and change all versions of a program--to make sure it remains free
software for all its users.

  When we speak of free software, we are referring to freedom, not
price.  Our General Public Licenses are designed to make sure that you
have the freedom to distribute copies of free software (and charge for
them if you wish), that you receive source code or can get it if you
want it, that you can change the software or use pieces of it in new
free programs, and that you know you can do these things.

  Developers that use our General Public Licenses protect your rights
with two steps: (1) assert copyright on the software, and (2) offer
you this License which gives you legal permission to copy, distribute
and/or modify the software.

  A secondary benefit of defending all users' freedom is that
improvements made in alternate versions of the program, if they
receive widespread use, become available for other developers to
incorporate.  Many developers of free software are heartened and
encouraged by the resulting cooperation.  However, in the case of
software used on network servers, this result may fail to come about.
The GNU General Public License permits making a modified version and
letting the public access it on a server without ever releasing its
source code to the public.

  The GNU Affero General Public License is designed specifically to
ensure that, in such cases, the modified source code becomes available
to the community.  It requires the operator of a network server to
provide the source code of the modified version running there to the
users of that server.  Therefore, public use of a modified version, on
a publicly accessible server, gives the public access to the source
code of the modified version.

  An older license, called the Affero General Public License and
published by Affero, was designed to accomplish similar goals.  This is
a different license, not a version of the Affero GPL, but Affero has
released a new version of the Affero GPL which permits relicensing under
this license.

  The precise terms and conditions for copying, distribution and
modification follow.

                       TERMS AND CONDITIONS

  0. Definitions.

  "This License" refers to version 3 of the GNU Affero General Public License.

  "Copyright" also means copyright-like laws that apply to other kinds of
works, such as semiconductor masks.

  "The Program" refers to any copyrightable work licensed under this
License.  Each licensee is addressed as "you".  "Licensees" and
"recipients" may be individuals or organizations.

  To "modify" a work means to copy from or adapt all or part of the work
in a fashion requiring copyright permission, other than the making of an
exact copy.  The resulting work is called a "modified version" of the
earlier work or a work "based on" the earlier work.

  A "covered work" means either the unmodified Program or a work based
on the Program.

  To "propagate" a work means to do anything with it that, without
permission, would make you directly or secondarily liable for
infringement under applicable copyright law, except executing it on a
computer or modifying a private copy.  Propagation includes copying,
distribution (with or without modification), making available to the
public, and in some countries other activities as well.

  To "convey" a work means any kind of propagation that enables other
parties to make or receive copies.  Mere interaction with a user through
a computer network, with no transfer of a copy, is not conveying.

  An interactive user interface displays "Appropriate Legal Notices"
to the extent that it includes a convenient and prominently visible
feature that (1) displays an appropriate copyright notice, and (2)
tells the user that there is no warranty for the work (except to the
extent that warranties are provided), that licensees may convey the
work under this License, and how to view a copy of this License.  If
the interface presents a list of user commands or options, such as a
menu, a prominent item in the list meets this criterion.

  1. Source Code.

  The "source code" for a work means the preferred form of the work
for making modifications to it.  "Object code" means any non-source
form of a work.

  A "Standard Interface" means an interface that either is an official
standard defined by a recognized standards body, or, in the case of
interfaces specified for a particular programming language, one that
is widely used among developers working in that language.

  The "System Libraries" of an executable work include anything, other
than the work as a whole, that (a) is included in the normal form of
packaging a Major Component, but which is not part of that Major
Component, and (b) serves only to enable use of the work with that
Major Component, or to implement a Standard Interface for which an
implementation is available to the public in source code form.  A
"Major Component", in this context, means a major essential component
(kernel, window system, and so on) of the specific operating system
(if any) on which the executable work runs, or a compiler used to
produce the work, or an object code interpreter used to run it.

  The "Corresponding Source" for a work in object code form means all
the source code needed to generate, install, and (for an executable
work) run the object code and to modify the work, including scripts to
control those activities.  However, it does not include the work's
System Libraries, or general-purpose tools or generally available free
programs which are used unmodified in performing those activities but
which are not part of the work.  For example, Corresponding Source
includes interface definition files associated with source files for
the work, and the source code for shared libraries and dynamically
linked subprograms that the work is specifically designed to require,
such as by intimate data communication or control flow between those
subprograms and other parts of the work.

  The Corresponding Source need not include anything that users
can regenerate automatically from other parts of the Corresponding
Source.

  The Corresponding Source for a work in source code form is that
same work.

  2. Basic Permissions.

  All rights granted under this License are granted for the term of
copyright on the Program, and are irrevocable provided the stated
conditions are met.  This License explicitly affirms your unlimited
permission to run the unmodified Program.  The output from running a
covered work is covered by this License only if the output, given its
content, constitutes a covered work.  This License acknowledges your
rights of fair use or other equivalent, as provided by copyright law.

  You may make, run and propagate covered works that you do not
convey, without conditions so long as your license otherwise remains
in force.  You may convey covered works to others for the sole purpose
of having them make modifications exclusively for you, or provide you
with facilities for running those works, provided that you comply with
the terms of this License in conveying all material for which you do
not control copyright.  Those thus making or running the covered works
for you must do so exclusively on your behalf, under your direction
and control, on terms that prohibit them from making any copies of
your copyrighted material outside their relationship with you.

  Conveying under any other circumstances is permitted solely under
the conditions stated below.  Sublicensing is not allowed; section 10
makes it unnecessary.

  3. Protecting Users' Legal Rights From Anti-Circumvention Law.

  No covered work shall be deemed part of an effective technological
measure under any applicable law fulfilling obligations under article
11 of the WIPO copyright treaty adopted on 20 December 1996, or
similar laws prohibiting or restricting circumvention of such
measures.

  When you convey a covered work, you waive any legal power to forbid
circumvention of technological measures to the extent such circumvention
is effected by exercising rights under this License with respect to
the covered work, and you disclaim any intention to limit operation or
modification of the work as a means of enforcing, against the work's
users, your or third parties' legal rights to forbid circumvention of
technological measures.

  4. Conveying Verbatim Copies.

  You may convey verbatim copies of the Program's source code as you
receive it, in any medium, provided that you conspicuously and
appropriately publish on each copy an appropriate copyright notice;
keep intact all notices stating that this License and any
non-permissive terms added in accord with section 7 apply to the code;
keep intact all notices of the absence of any warranty; and give all
recipients a copy of this License along with the Program.

  You may charge any price or no price for each copy that you convey,
and you may offer support or warranty protection for a fee.

  5. Conveying Modified Source Versions.

  You may convey a work based on the Program, or the modifications to
produce it from the Program, in the form of source code under the
terms of section 4, provided that you also meet all of these conditions:

    a) The work must carry prominent notices stating that you modified
    it, and giving a relevant date.

    b) The work must carry prominent notices stating that it is
    released under this License and any conditions added under section
    7.  This requirement modifies the requirement in section 4 to
    "keep intact all notices".

    c) You must license the entire work, as a whole, under this
    License to anyone who comes into possession of a copy.  This
    License will therefore apply, along with any applicable section 7
    additional terms, to the whole of the work, and all its parts,
    regardless of how they are packaged.  This License gives no
    permission to license the work in any other way, but it does not
    invalidate such permission if you have separately received it.

    d) If the work has interactive user interfaces, each must display
    Appropriate Legal Notices; however, if the Program has interactive
    interfaces that do not display Appropriate Legal Notices, your
    work need not make them do so.

  A compilation of a covered work with other separate and independent
works, which are not by their nature extensions of the covered work,
and which are not combined with it such as to form a larger program,
in or on a volume of a storage or distribution medium, is called an
"aggregate" if the compilation and its resulting copyright are not
used to limit the access or legal rights of the compilation's users
beyond what the individual works permit.  Inclusion of a covered work
in an aggregate does not cause this License to apply to the other
parts of the aggregate.

  6. Conveying Non-Source Forms.

  You may convey a covered work in object code form under the terms
of sections 4 and 5, provided that you also convey the
machine-readable Corresponding Source under the terms of this License,
in one of these ways:

    a) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by the
    Corresponding Source fixed on a durable physical medium
    customarily used for software interchange.

    b) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by a
    written offer, valid for at least three years and valid for as
    long as you offer spare parts or customer support for that product
    model, to give anyone who possesses the object code either (1) a
    copy of the Corresponding Source for all the software in the
    product that is covered by this License, on a durable physical
    medium customarily used for software interchange, for a price no
    more than your reasonable cost of physically performing this
    conveying of source, or (2) access to copy the
    Corresponding Source from a network server at no charge.

    c) Convey individual copies of the object code with a copy of the
    written offer to provide the Corresponding Source.  This
    alternative is allowed only occasionally and noncommercially, and
    only if you received the object code with such an offer, in accord
    with subsection 6b.

    d) Convey the object code by offering access from a designated
    place (gratis or for a charge), and offer equivalent access to the
    Corresponding Source in the same way through the same place at no
    further charge.  You need not require recipients to copy the
    Corresponding Source along with the object code.  If the place to
    copy the object code is a network server, the Corresponding Source
    may be on a different server (operated by you or a third party)
    that supports equivalent copying facilities, provided you maintain
    clear directions next to the object code saying where to find the
    Corresponding Source.  Regardless of what server hosts the
    Corresponding Source, you remain obligated to ensure that it is
    available for as long as needed to satisfy these requirements.

    e) Convey the object code using peer-to-peer transmission, provided
    you inform other peers where the object code and Corresponding
    Source of the work are being offered to the general public at no
    charge under subsection 6d.

  A separable portion of the object code, whose source code is excluded
from the Corresponding Source as a System Library, need not be
included in conveying the object code work.

  A "User Product" is either (1) a "consumer product", which means any
tangible personal property which is normally used for personal, family,
or household purposes, or (2) anything designed or sold for incorporation
into a dwelling.  In determining whether a product is a consumer product,
doubtful cases shall be resolved in favor of coverage.  For a particular
product received by a particular user, "normally used" refers to a
typical or common use of that class of product, regardless of the status
of the particular user or of the way in which the particular user
actually uses, or expects or is expected to use, the product.  A product
is a consumer product regardless of whether the product has substantial
commercial, industrial or non-consumer uses, unless such uses represent
the only significant mode of use of the product.

  "Installation Information" for a User Product means any methods,
procedures, authorization keys, or other information required to install
and execute modified versions of a covered work in that User Product from
a modified version of its Corresponding Source.  The information must
suffice to ensure that the continued functioning of the modified object
code is in no case prevented or interfered with solely because
modification has been made.

  If you convey an object code work under this section in, or with, or
specifically for use in, a User Product, and the conveying occurs as
part of a transaction in which the right of possession and use of the
User Product is transferred to the recipient in perpetuity or for a
fixed term (regardless of how the transaction is characterized), the
Corresponding Source conveyed under this section must be accompanied
by the Installation Information.  But this requirement does not apply
if neither you nor any third party retains the ability to install
modified object code on the User Product (for example, the work has
been installed in ROM).

  The requirement to provide Installation Information does not include a
requirement to continue to provide support service, warranty, or updates
for a work that has been modified or installed by the recipient, or for
the User Product in which it has been modified or installed.  Access to a
network may be denied when the modification itself materially and
adversely affects the operation of the network or violates the rules and
protocols for communication across the network.

  Corresponding Source conveyed, and Installation Information provided,
in accord with this section must be in a format that is publicly
documented (and with an implementation available to the public in
source code form), and must require no special password or key for
unpacking, reading or copying.

  7. Additional Terms.

  "Additional permissions" are terms that supplement the terms of this
License by making exceptions from one or more of its conditions.
Additional permissions that are applicable to the entire Program shall
be treated as though they were included in this License, to the extent
that they are valid under applicable law.  If additional permissions
apply only to part of the Program, that part may be used separately
under those permissions, but the entire Program remains governed by
this License without regard to the additional permissions.

  When you convey a copy of a covered work, you may at your option
remove any additional permissions from that copy, or from any part of
it.  (Additional permissions may be written to require their own
removal in certain cases when you modify the work.)  You may place
additional permissions on material, added by you to a covered work,
for which you have or can give appropriate copyright permission.

  Notwithstanding any other provision of this License, for material you
add to a covered work, you may (if authorized by the copyright holders of
that material) supplement the terms of this License with terms:

    a) Disclaiming warranty or limiting liability differently from the
    terms of sections 15 and 16 of this License; or

    b) Requiring preservation of specified reasonable legal notices or
    author attributions in that material or in the Appropriate Legal
    Notices displayed by works containing it; or

    c) Prohibiting misrepresentation of the origin of that material, or
    requiring that modified versions of such material be marked in
    reasonable ways as different from the original version; or

    d) Limiting the use for publicity purposes of names of licensors or
    authors of the material; or

    e) Declining to grant rights under trademark law for use of some
    trade names, trademarks, or service marks; or

    f) Requiring indemnification of licensors and authors of that
    material by anyone who conveys the material (or modified versions of
    it) with contractual assumptions of liability to the recipient, for
    any liability that these contractual assumptions directly impose on
    those licensors and authors.

  All other non-permissive additional terms are considered "further
restrictions" within the meaning of section 10.  If the Program as you
received it, or any part of it, contains a notice stating that it is
governed by this License along with a term that is a further
restriction, you may remove that term.  If a license document contains
a further restriction but permits relicensing or conveying under this
License, you may add to a covered work material governed by the terms
of that license document, provided that the further restriction does
not survive such relicensing or conveying.

  If you add terms to a covered work in accord with this section, you
must place, in the relevant source files, a statement of the
additional terms that apply to those files, or a notice indicating
where to find the applicable terms.

  Additional terms, permissive or non-permissive, may be stated in the
form of a separately written license, or stated as exceptions;
the above requirements apply either way.

  8. Termination.

  You may not propagate or modify a covered work except as expressly
provided under this License.  Any attempt otherwise to propagate or
modify it is void, and will automatically terminate your rights under
this License (including any patent licenses granted under the third
paragraph of section 11).

  However, if you cease all violation of this License, then your
license from a particular copyright holder is reinstated (a)
provisionally, unless and until the copyright holder explicitly and
finally terminates your license, and (b) permanently, if the copyright
holder fails to notify you of the violation by some reasonable means
prior to 60 days after the cessation.

  Moreover, your license from a particular copyright holder is
reinstated permanently if the copyright holder notifies you of the
violation by some reasonable means, this is the first time you have
received notice of violation of this License (for any work) from that
copyright holder, and you cure the violation prior to 30 days after
your receipt of the notice.

  Termination of your rights under this section does not terminate the
licenses of parties who have received copies or rights from you under
this License.  If your rights have been terminated and not permanently
reinstated, you do not qualify to receive new licenses for the same
material under section 10.

  9. Acceptance Not Required for Having Copies.

  You are not required to accept this License in order to receive or
run a copy of the Program.  Ancillary propagation of a covered work
occurring solely as a consequence of using peer-to-peer transmission
to receive a copy likewise does not require acceptance.  However,
nothing other than this License grants you permission to propagate or
modify any covered work.  These actions infringe copyright if you do
not accept this License.  Therefore, by modifying or propagating a
covered work, you indicate your acceptance of this License to do so.

  10. Automatic Licensing of Downstream Recipients.

  Each time you convey a covered work, the recipient automatically
receives a license from the original licensors, to run, modify and
propagate that work, subject to this License.  You are not responsible
for enforcing compliance by third parties with this License.

  An "entity transaction" is a transaction transferring control of an
organization, or substantially all assets of one, or subdividing an
organization, or merging organizations.  If propagation of a covered
work results from an entity transaction, each party to that
transaction who receives a copy of the work also receives whatever
licenses to the work the party's predecessor in interest had or could
give under the previous paragraph, plus a right to possession of the
Corresponding Source of the work from the predecessor in interest, if
the predecessor has it or can get it with reasonable efforts.

  You may not impose any further restrictions on the exercise of the
rights granted or affirmed under this License.  For example, you may
not impose a license fee, royalty, or other charge for exercise of
rights granted under this License, and you may not initiate litigation
(including a cross-claim or counterclaim in a lawsuit) alleging that
any patent claim is infringed by making, using, selling, offering for
sale, or importing the Program or any portion of it.

  11. Patents.

  A "contributor" is a copyright holder who authorizes use under this
License of the Program or a work on which the Program is based.  The
work thus licensed is called the contributor's "contributor version".

  A contributor's "essential patent claims" are all patent claims
owned or controlled by the contributor, whether already acquired or
hereafter acquired, that would be infringed by some manner, permitted
by this License, of making, using, or selling its contributor version,
but do not include claims that would be infringed only as a
consequence of further modification of the contributor version.  For
purposes of this definition, "control" includes the right to grant
patent sublicenses in a manner consistent with the requirements of
this License.

  Each contributor grants you a non-exclusive, worldwide, royalty-free
patent license under the contributor's essential patent claims, to
make, use, sell, offer for sale, import and otherwise run, modify and
propagate the contents of its contributor version.

  In the following three paragraphs, a "patent license" is any express
agreement or commitment, however denominated, not to enforce a patent
(such as an express permission to practice a patent or covenant not to
sue for patent infringement).  To "grant" such a patent license to a
party means to make such an agreement or commitment not to enforce a
patent against the party.

  If you convey a covered work, knowingly relying on a patent license,
and the Corresponding Source of the work is not available for anyone
to copy, free of charge and under the terms of this License, through a
publicly available network server or other readily accessible means,
then you must either (1) cause the Corresponding Source to be so
available, or (2) arrange to deprive yourself of the benefit of the
patent license for this particular work, or (3) arrange, in a manner
consistent with the requirements of this License, to extend the patent
license to downstream recipients.  "Knowingly relying" means you have
actual knowledge that, but for the patent license, your conveying the
covered work in a country, or your recipient's use of the covered work
in a country, would infringe one or more identifiable patents in that
country that you have reason to believe are valid.

  If, pursuant to or in connection with a single transaction or
arrangement, you convey, or propagate by procuring conveyance of, a
covered work, and grant a patent license to some of the parties
receiving the covered work authorizing them to use, propagate, modify
or convey a specific copy of the covered work, then the patent license
you grant is automatically extended to all recipients of the covered
work and works based on it.

  A patent license is "discriminatory" if it does not include within
the scope of its coverage, prohibits the exercise of, or is
conditioned on the non-exercise of one or more of the rights that are
specifically granted under this License.  You may not convey a covered
work if you are a party to an arrangement with a third party that is
in the business of distributing software, under which you make payment
to the third party based on the extent of your activity of conveying
the work, and under which the third party grants, to any of the
parties who would receive the covered work from you, a discriminatory
patent license (a) in connection with copies of the covered work
conveyed by you (or copies made from those copies), or (b) primarily
for and in connection with specific products or compilations that
contain the covered work, unless you entered into that arrangement,
or that patent license was granted, prior to 28 March 2007.

  Nothing in this License shall be construed as excluding or limiting
any implied license or other defenses to infringement that may
otherwise be available to you under applicable patent law.

  12. No Surrender of Others' Freedom.

  If conditions are imposed on you (whether by court order, agreement or
otherwise) that contradict the conditions of this License, they do not
excuse you from the conditions of this License.  If you cannot convey a
covered work so as to satisfy simultaneously your obligations under this
License and any other pertinent obligations, then as a consequence you may
not convey it at all.  For example, if you agree to terms that obligate you
to collect a royalty for further conveying from those to whom you convey
the Program, the only way you could satisfy both those terms and this
License would be to refrain entirely from conveying the Program.

  13. Remote Network Interaction; Use with the GNU General Public License.

  Notwithstanding any other provision of this License, if you modify the
Program, your modified version must prominently offer all users
interacting with it remotely through a computer network (if your version
supports such interaction) an opportunity to receive the Corresponding
Source of your version by providing access to the Corresponding Source
from a network server at no charge, through some standard or customary
means of facilitating copying of software.  This Corresponding Source
shall include the Corresponding Source for any work covered by version 3
of the GNU General Public License that is incorporated pursuant to the
following paragraph.

  Notwithstanding any other provision of this License, you have
permission to link or combine any covered work with a work licensed
under version 3 of the GNU General Public License into a single
combined work, and to convey the resulting work.  The terms of this
License will continue to apply to the part which is the covered work,
but the work with which it is combined will remain governed by version
3 of the GNU General Public License.

  14. Revised Versions of this License.

  The Free Software Foundation may publish revised and/or new versions of
the GNU Affero General Public License from time to time.  Such new versions
will be similar in spirit to the present version, but may differ in detail to
address new problems or concerns.

  Each version is given a distinguishing version number.  If the
Program specifies that a certain numbered version of the GNU Affero General
Public License "or any later version" applies to it, you have the
option of following the terms and conditions either of that numbered
version or of any later version published by the Free Software
Foundation.  If the Program does not specify a version number of the
GNU Affero General Public License, you may choose any version ever published
by the Free Software Foundation.

  If the Program specifies that a proxy can decide which future
versions of the GNU Affero General Public License can be used, that proxy's
public statement of acceptance of a version permanently authorizes you
to choose that version for the Program.

  Later license versions may give you additional or different
permissions.  However, no additional obligations are imposed on any
author or copyright holder as a result of your choosing to follow a
later version.

  15. Disclaimer of Warranty.

  THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY
APPLICABLE LAW.  EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT
HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY
OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE.  THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM
IS WITH YOU.  SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF
ALL NECESSARY SERVICING, REPAIR OR CORRECTION.

  16. Limitation of Liability.

  IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN WRITING
WILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MODIFIES AND/OR CONVEYS
THE PROGRAM AS PERMITTED ABOVE, BE LIABLE TO YOU FOR DAMAGES, INCLUDING ANY
GENERAL, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING OUT OF THE
USE OR INABILITY TO USE THE PROGRAM (INCLUDING BUT NOT LIMITED TO LOSS OF
DATA OR DATA BEING RENDERED INACCURATE OR LOSSES SUSTAINED BY YOU OR THIRD
PARTIES OR A FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER PROGRAMS),
EVEN IF SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF
SUCH DAMAGES.

  17. Interpretation of Sections 15 and 16.

  If the disclaimer of warranty and limitation of liability provided
above cannot be given local legal effect according to their terms,
reviewing courts shall apply local law that most closely approximates
an absolute waiver of all civil liability in connection with the
Program, unless a warranty or assumption of liability accompanies a
copy of the Program in return for a fee.

                     END OF TERMS AND CONDITIONS

            How to Apply These Terms to Your New Programs

  If you develop a new program, and you want it to be of the greatest
possible use to the public, the best way to achieve this is to make it
free software which everyone can redistribute and change under these terms.

  To do so, attach the following notices to the program.  It is safest
to attach them to the start of each source file to most effectively
state the exclusion of warranty; and each file should have at least
the "copyright" line and a pointer to where the full notice is found.

    <one line to give the program's name and a brief idea of what it does.>
    Copyright (C) <year>  <name of author>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

Also add information on how to contact you by electronic and paper mail.

  If your software can interact with users remotely through a computer
network, you should also make sure that it provides a way for users to
get its source.  For example, if your program is a web application, its
interface could display a "Source" link that leads users to an archive
of the code.  There are many ways you could offer source, and different
solutions will be better for different programs; see section 13 for the
specific requirements.

  You should also get your employer (if you work as a programmer) or school,
if any, to sign a "copyright disclaimer" for the program, if necessary.
For more information on this, and how to apply and follow the GNU AGPL, see
<https://www.gnu.org/licenses/>.
"""

    #Delete any mention of "README_STRING" or "LICENSE_STRING"
    #and "SOURCE_CODE_STRING" from "SOURCE_CODE_STRING", as you 
    #only want the Python code in there. Also, make sure to use
    #a raw string (r""" """) in order to avoid interpreting 
    #backslashes ("\") as escape characters.
    SOURCE_CODE_STRING = textwrap.dedent(r"""import csv
from datetime import datetime
import io
import mutagen
from mutagen.flac import Picture
import os
from PIL import Image
import re
import shutil
import signal
import subprocess
import sys
import textwrap
import time
import traceback


#The "clear_screen()" function will clear the CLI screen
#using the appropriate command depending on the operating system.
def clear_screen():
    #'nt' is for Windows, 'posix is for Linux/Raspberry Pi/macOS (else statement)
    os.system('cls' if os.name == 'nt' else 'clear')

#The Signal Interrupt (SIGINT) handler will
#call the "signal_interrupt_signal_handler()" function 
#when the user presses on CTRL + C to exit the app.

#The function "signal_interrupt_signal_handler()" will call
#"sys.exit(0)" to exit the program normally.
def signal_interrupt_signal_handler(sig, frame):
    sys.exit(0)

#The function "write_entry_in_error_log()" will write 
#the full technical traceback error to the error log.
def write_entry_in_error_log():
    with open("ERROR LOG.txt", "a", encoding="utf-8") as error_log:
        error_log.write(f"\n--- Error at {datetime.now()} ---\n")
        traceback.print_exc(file=error_log)

#The function "display_progress()" will display the progress string in the console
#and return the estimated number of seconds for the code to complete.
def display_progress(current_midi_index, first_midi_index, last_midi_index, start_time, previous_estimated_seconds):
            
    elapsed_seconds = time.perf_counter() - start_time
    #divmod returns (minutes, remaining_seconds)
    mins, secs = divmod(round(elapsed_seconds), 60)
    time_string = f"{mins:02}:{secs:02}"
    eta_string = ""

    #If the MIDI file will only be comprised of one scoresheet 
    #scan, then the "percent_completion" will be 100% after 
    #processing that MIDI file (so as to avoid "Division 
    #by Zero" errors).
    if last_midi_index - first_midi_index == 0:
        percent_completion = 100
        eta_string = f" ETA: 00:00\n"
    else:
        #The percent completion is calculated by dividing the one-indexed current MIDI index (hence the "+1")
        #by the total number of MIDI files to be processed, equals the value of "last_midi_index" plus one.
        #The resulting quotient is multiplied by 100 and then rounded when printed on-screen.
        percent_completion = (current_midi_index+1)/(last_midi_index+1) * 100

    #The previous estimation of the remaining number of seconds is stored in the variable
    #"previous_estimated_seconds" and will be used instead of the current calculation
    #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
    #its estimation.
    estimated_seconds = previous_estimated_seconds
    #A delay of 3 MIDI files is used to be able to gather a somewhat accurate value
    #of the elapsed time for a given percent completion value.
    if (last_midi_index > first_midi_index + 3 and current_midi_index > first_midi_index + 3):
        #The estimated number of seconds left is calculated by doing the cross-multiplication between
        #the number of percentage points left to reach completion ("100 - percent_completion") 
        #and the elapsed time for the current percent completion.
        estimated_seconds = round((100 - percent_completion) * elapsed_seconds / percent_completion)
        #The previous estimation of the remaining number of seconds is stored in the variable
        #"previous_estimated_seconds" and will be used instead of the current calculation
        #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
        #its estimation.
        if (previous_estimated_seconds != 0 and estimated_seconds > previous_estimated_seconds):
            estimated_seconds = previous_estimated_seconds

        #If the current MIDI index is the last MIDI index,
        #then the remaining time is zero seconds (" ETA: 00:00").
        if (current_midi_index == last_midi_index):
            percent_completion = 100
            eta_string = f" ETA: 00:00\n"
        #We do not want to display negative times, hence the
        #condition ("elif (estimated_seconds > 0)").
        elif (estimated_seconds > 0):
            eta_mins, eta_secs = divmod(round(estimated_seconds), 60)
            eta_string = f" ETA: {eta_mins:02}:{eta_secs:02}"

    #"\r" resets the line
    sys.stdout.write(f"\rRendered MIDI file: {current_midi_index+1} of {last_midi_index+1} ({round(percent_completion)}%) Time: {time_string}{eta_string}")

    return estimated_seconds

#The function "get_terminal_dimensions()" will return the number of columns 
#and rows in the console, to allow to properly format the text and dividers.
def get_terminal_dimensions():
    #Detect columns (width) and lines (height)
    #Returns a named tuple; default fallback is (80, 24)
    size = shutil.get_terminal_size(fallback=(80, 24))
    return int(size.columns * 0.75), int(size.lines)
     

if __name__ == '__main__':
    
    #The "clear_screen()" function will clear the CLI screen
    #using the appropriate command depending on the operating system.
    clear_screen()
    
    metadata_csv_folder_name = "Metadata CSV File"
    album_cover_image_folder_name = "Album Cover Image"
    sf2_folder_name = "SF2 Files"
    midi_folder_name = "MIDI Files"
    output_flac_folder_name = "Generated FLAC Files"
    press_any_key_string = "Press any key to continue." 
    sample_rate = "44100"
    #The default gain of FluidSynth is 0.2, with 
    #possible values spanning 0.0 to 10.0, inclusively,
    #and larger values resulting in louder output.
    #The gain needs to be specified in the file names 
    #of the SF2 files, separated by a hyphen, and must 
    #always be written in floating point format
    #(e.g., "piano - 1.0.sf2").
    default_gain_value = "0.2"
    debug_mode = False
    cover_image_description = ""
    img_size_kilobyte_threshold = 500
    img_dimension_pixel_threshold = 800
    metadata_dict = {}
    #The Boolean variable "has_user_passed_in_image_description_argument",
    #initialized to "False" will be set to "True" should the user have 
    #passed in a cover image description after the "image_description:"
    #argument when running the code. This Boolean variable, when set 
    #to "True" will prevent the code from extracting the cover image 
    #description text form the PNG or JPEG image file name.
    has_user_passed_in_image_description_argument = False
    
    #The function "get_terminal_dimensions()" will return the number of columns 
    #and rows in the console, to allow to properly format the text and dividers.
    columns, lines = get_terminal_dimensions()
    
    if len(sys.argv) > 1:
        #The "try/except" statement will
        #intercept any "ValueErrors" and
        #ask the users to correctly enter
        #the desired values for the variables
        #directly after the colon separating
        #the variable name from the value.
        try:  
            for i in range(1, len(sys.argv)):
                argv_strip_lower = sys.argv[i].strip().lower()
                if argv_strip_lower[:12] == "sample_rate:":
                    sample_rate = argv_strip_lower[12:].strip()
                elif argv_strip_lower[:18] == "target_image_size:":
                    img_size_kilobyte_threshold = int(argv_strip_lower[18:].strip())    
                elif argv_strip_lower[:23] == "target_image_dimension:":
                    img_dimension_pixel_threshold = int(argv_strip_lower[23:].strip())
                elif argv_strip_lower[:18] == "image_description:":
                    #"sys.argv[i].strip()" is used instead of "argv_strip_lower",
                    #as we want to preserve the case information in the original string.
                    cover_image_description = sys.argv[i].strip()[18:].strip()
                    #The Boolean variable "has_user_passed_in_image_description_argument",
                    #initialized to "False" will be set to "True" should the user have 
                    #passed in a cover image description after the "image_description:"
                    #argument when running the code. This Boolean variable, when set 
                    #to "True" will prevent the code from extracting the cover image 
                    #description text form the PNG or JPEG image file name.
                    has_user_passed_in_image_description_argument = True
                elif argv_strip_lower[:10] == "debug_mode":
                    debug_mode = True
                    
        except Exception as e:
            print(e)
            
            print("\n" + textwrap.fill('Please enter the name of the parameter you wish to alter, followed ' +
            'by a colon, and the desired setting directly after the colon. For example, ' +
            'to set the target cover image size to 200 KB, you would enter: "target_image_size:200".', columns) + "\n")
            input(press_any_key_string)
            sys.exit(1)

    try:    
        cwd = os.getcwd()

        #The FluidSynth executable will be located 
        #through an "os.walk()" method and its path 
        #will be stored in the "fluidsynth_executable_path"
        #variable.
        fluidsynth_executable_name = "fluidsynth.exe"
        fluidsynth_executable_path = ""
        for root, dirs, files in os.walk(cwd):
            if fluidsynth_executable_name in files:
                fluidsynth_executable_path = os.path.join(root, fluidsynth_executable_name)
        #If the FluidSynth executable could not be located 
        #in the working folder, then an error message will 
        #be printed on-screen.        
        if not fluidsynth_executable_path:
            print("\n" + textwrap.fill("Please include the FluidSynth binary folder in the working folder. As of October 2026, only the FluidSynth versions up to 2.3.0 allow to reliably render MIDI files without appending extra silence to the end of the rendered audio files (see Issue #1408 of the FluidSynth GitHub for more details). You should then select one of these versions from the following link: https://github.com/FluidSynth/fluidsynth/releases.", columns) + "\n")
            input(press_any_key_string)
            sys.exit(1)
 
        #Register the Signal Interrupt (SIGINT) handler that will
        #call the "signal_interrupt_signal_handler()" function 
        #when the user presses on CTRL + C to exit the app.

        #The function "signal_interrupt_signal_handler()" will call
        #"sys.exit(0)" to exit the program normally.
        signal.signal(signal.SIGINT, signal_interrupt_signal_handler)
        
        #For more metadata tags, please consult the following link:
        #https://picard-docs.musicbrainz.org/en/latest/variables/tags_basic.html
        default_csv_file_list = [["album", ""], ["artist", ""], ["comment", ""], ["copyright", ""], ["genre", ""], 
        ["language", ""], ["totaltracks", ""], ["website", ""], ["year", ""]]
        
        csv_folder_path = os.path.join(cwd, metadata_csv_folder_name)
        #If the "Metadata CSV File" subfolder doesn't already exist 
        #in the working folder, then it will be created, and a blank 
        #copy of the default CSV file (without values) will be added 
        #to it.
        if not os.path.exists(csv_folder_path):
            os.mkdir(csv_folder_path)
            #The 'newline=""' argument prevents Windows 
            #from including empty lines between rows.
            with open(os.path.join(csv_folder_path, "metadata_csv_file.csv"), mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter="\t")
                writer.writerows(default_csv_file_list)
        #Otherwise the CSV file names will be collated, and if there is only 
        #one CSV file within the "Metadata CSV File" subfolder, then the 
        #metadata information will be extracted from it.
        else:
            #Get a list of ".csv" file names in the "Metadata CSV File" subfolder of the working folder
            csv_file_names = [file_name for file_name in sorted(os.listdir(csv_folder_path)) if file_name[-4:] == ".csv"]
            #If the has included more than one CSV file in the "Metadata CSV File" subfolder,
            #they will be prompted to only include one such file in that folder.
            if len(csv_file_names) > 1:
                too_many_csv_files_string = "\n" + textwrap.fill(f"Please add a single CSV file in the '{metadata_csv_folder_name}' subfolder of the 'midi2flac' folder and launch the application again. A blank CSV file with no values for the metadata tags will be generated automatically should you delete the {metadata_csv_folder_name}.", width=columns) + "\n"     
                print(too_many_csv_files_string)
                input(press_any_key_string)
                sys.exit(1)
            #If the "Metadata CSV File" subfolder doesn't already contain 
            #a CSV file, then a blank copy of the default CSV file (without values) 
            #will be added to it.
            elif len(csv_file_names) == 0:
                #The 'newline=""' argument prevents Windows 
                #from including empty lines between rows.
                with open(os.path.join(csv_folder_path, "metadata_csv_file.csv"), mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f, delimiter="\t")
                    writer.writerows(default_csv_file_list)
            #Otherwise the CSV file will be opened and the metadata information 
            #for each key will be stored in the "metadata_dict" dictionary, 
            #provided that the stripped value for that key isn't equal to 
            #an empty string, meaning that the user didn't provide a value 
            #there.
            else:
                with open(os.path.join(csv_folder_path, "metadata_csv_file.csv"), mode="r", newline="", encoding="utf-8") as f:
                    reader = csv.reader(f, delimiter="\t")
                    for row in reader:
                        if len(row) > 1 and row[1].strip() != "":
                            metadata_dict[row[0]] = row[1]
                        
        album_cover_image_folder_path = os.path.join(cwd, album_cover_image_folder_name)
        png_file_names = []
        album_cover_image_file_path = ""
        album_cover_image_file_name_without_extension = ""
        mime_value = ""
        #If the "Album Cover Image" subfolder of the working folder 
        #doesn't already exist, then it will be created.
        if not os.path.exists(album_cover_image_folder_path):
            os.mkdir(album_cover_image_folder_path)
        #This "else" statement will first look for any JPEG images within 
        #the "Album Cover Image" subfolder. If none are found, then the 
        #code will look for PNG images instead.
        else:
            #Get a list of ".jpg" file names in the "Album Cover Image" subfolder of the working folder
            jpg_file_names = [file_name for file_name in sorted(os.listdir(album_cover_image_folder_path)) if file_name[-4:] == ".jpg"]
            #If at least one JPEG image was present in the "Album Cover Image",
            #then the "if" statement below will store the first JPEG image's 
            #path in the "album_cover_image_file_path" variable, and the 
            #JPEG file's name in the "album_cover_image_file_name_without_extension"
            #variable (minus the ".jpg" extension). The value of "mime_value" will 
            #then be set to "image/jpeg".
            if jpg_file_names != []:
                album_cover_image_file_path = os.path.join(cwd, album_cover_image_folder_path, jpg_file_names[0])
                album_cover_image_file_name_without_extension = jpg_file_names[0][:-4]
                mime_value = "image/jpeg"
            #A similar approach is taken for PNG image files.
            else:
                #Get a list of ".png" file names in the "Album Cover Image" subfolder of the working folder
                png_file_names = [file_name for file_name in sorted(os.listdir(album_cover_image_folder_path)) if file_name[-4:] == ".png"]
                if png_file_names != []:
                    album_cover_image_file_path = os.path.join(cwd, album_cover_image_folder_path, png_file_names[0]) 
                    album_cover_image_file_name_without_extension = png_file_names[0][:-4]
                    mime_value = "image/png" 

        #If an album cover image was found in the "Album Cover Image" 
        #subfolder of the working folder, then the following "if" 
        #statement will run.
        if album_cover_image_file_path != "":
            #The Boolean variable "has_user_passed_in_image_description_argument",
            #initialized to "False" will be set to "True" should the user have 
            #passed in a cover image description after the "image_description:"
            #argument when running the code. This Boolean variable, when set 
            #to "True" will prevent the code from extracting the cover image 
            #description text form the PNG or JPEG image file name.
            if not has_user_passed_in_image_description_argument:
                cover_image_description = album_cover_image_file_name_without_extension
            
            #The dictionary "img_mode_to_bit_depth_dict" will allow to determine the bit-depth
            #of the cover image using the "Pillow" Python module based on the image mode 
            #(e.g., "1", "L", "P", "RGB" or "RGBA", with a fallback value of 24 bits).
            img_mode_to_bit_depth_dict = {"1": 1, "L": 8, "P": 8, "RGB": 24, "RGBA": 32}
            with Image.open(album_cover_image_file_path) as img:
                
                #For best results, the JPEG or PNG album cover image should meet the following criteria:
                #- File size under 1 MB (ideally under 500 KB)
                #- Resolution of 800x800 or 600x600 pixels. Many devices fail to render images larger than 1024x1024.
                #- The image should be saved in the standard sRGB color space (and not the CMYK color profile, which is meant for printing).
                
                #If the image mode isn't already "RGB" or "RGBA", 
                #then it will be set to "RGB".
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                #If the images are larger in dimension than the value of 
                #"img_dimension_pixel_threshold", they will be downscaled.
                if img.width > img_dimension_pixel_threshold or img_height > img_dimension_pixel_threshold:
                    img.thumbnail((img_dimension_pixel_threshold, img_dimension_pixel_threshold), Image.Resampling.LANCZOS)

                width, height = img.size
                #The dictionary "img_mode_to_bit_depth_dict" will allow to determine the bit-depth
                #of the cover image using the "Pillow" Python module based on the image mode 
                #(e.g., "1", "L", "P", "RGB" or "RGBA", with a fallback value of 24 bits).
                bit_depth = img_mode_to_bit_depth_dict.get(img.mode, 24)
                
                #Compress the image into memory buffer to meet file size restrictions 
                img_buffer = io.BytesIO()
                
                #In the case of JPEGs, start at a quality of 90%
                #and decrease by 5% until the image size meets the 
                #value of "img_size_kilobyte_threshold".
                if mime_value == "image/jpeg":
                    jpg_quality = 90
                    while jpg_quality > 50:
                        #Wipe the memory buffer before another 
                        #iteration of the "while" loop by first 
                        #going back to the very start of the image 
                        #("seek(0)", and then removing everything 
                        #in memory after that point ("truncate()").
                        img_buffer.seek(0)
                        img_buffer.truncate()
                        img.save(img_buffer, format="JPEG", quality=jpg_quality, optimize=True)
                        #If the size of the image in the buffer is smaller or equal to 
                        #the threshold number of kilobytes times 1024 bytes per kilobytes,
                        #then the "while" loop will break.
                        if img_buffer.tell() <= img_size_kilobyte_threshold * 1024:
                            break
                        jpg_quality -= 5                    
                else:
                    #For PNGs, use the maximum compression level, as it is a lossless format
                    img.save(img_buffer, format="PNG", optimize=True, compress_level=9)
                
                #Extract the optimized binary data:
                img_binary_data = img_buffer.getvalue()
            
            #A mutagen "Picture" object is instantiated, and its 
            #attributes are set to the values obtained with the 
            #Pillow Python module.
            album_cover_image = Picture()
            with open(album_cover_image_file_path, "rb") as f:
                album_cover_image.data = img_binary_data
                album_cover_image.type = mutagen.id3.PictureType.COVER_FRONT
                album_cover_image.mime = mime_value
                album_cover_image.desc = cover_image_description
                album_cover_image.width = width
                album_cover_image.height = height
                album_cover_image.depth = bit_depth
         
        #If either the "SF2 Files" subfolder is missing, or if it is empty,
        #it will be created and the code will exit the application while 
        #printing the "missing_sf2_files_string" on-screen.
        missing_sf2_files_string = "\n" + textwrap.fill("Please add the SF2 files in the 'SF2 Files' subfolder of the 'midi2flac' folder and launch the application again.", width=columns) + "\n"     
        
        #If either the "MIDI Files" subfolder is missing, or if it is empty,
        #it will be created and the code will exit the application while 
        #printing the "missing_midi_files_string" on-screen.
        missing_midi_files_string = "\n" + textwrap.fill("Please add the MIDI files in the 'MIDI Files' subfolder of the 'midi2flac' folder and launch the application again.", width=columns) + "\n"     
        
        output_flac_files_path = os.path.join(cwd, output_flac_folder_name)
        if not os.path.exists(output_flac_files_path):
            os.mkdir(output_flac_files_path)
         
        sf2_file_path = os.path.join(cwd, sf2_folder_name)
        if not os.path.exists(sf2_file_path):
            os.mkdir(sf2_file_path)
            print(missing_sf2_files_string)
            input(press_any_key_string)
            sys.exit(1)
        else:
            #Get a list of ".sf2" file names in the "SF2 Files" subfolder of the working folder
            sf2_file_names = [file_name for file_name in sorted(os.listdir(sf2_file_path)) if file_name[-4:] == ".sf2"]
            sf2_file_names_without_parenthesized_gain_expression = []
            sf2_gain_float_values = []
            if sf2_file_names == []:
                print(missing_sf2_files_string)
                input(press_any_key_string)
                sys.exit(1)
        
        #The default gain of FluidSynth is 0.2, with 
        #possible values spanning 0.0 to 10.0, inclusively,
        #and larger values resulting in louder output.
        #The gain needs to be specified in the file names 
        #of the SF2 files, separated by a hyphen, and must 
        #always be written in floating point format
        #(e.g., "piano - 1.0.sf2").
        
        #The regex pattern for the gain expression, including dividers 
        #such as hyphens, underscores and plus signs as well as spaces
        #will allow the code to extract the floating point value representing 
        #the gain setting.
        gain_expression_pattern = r"[ ]*[-_+]*[ ]*[\d]+\.[\d]+[ ]*[-_+]*[ ]*"
        for sf2_file_name in sf2_file_names:
            sf2_file_name_without_extension = sf2_file_name[:-4]
            gain_expression_hits = re.findall(gain_expression_pattern, sf2_file_name_without_extension)
            #If a gain expression was found, the floating point value will be extracted 
            #from it, and then appended to the list of gain values for each SF2 file 
            #("sf2_file_names_without_parenthesized_gain_expression").
            if gain_expression_hits != []:
                sf2_gain_float_values.append(re.findall(r"[\d]+\.[\d]+", gain_expression_hits[0])[0])
                sf2_file_names_without_parenthesized_gain_expression.append(re.sub(gain_expression_pattern, "", sf2_file_name_without_extension))
            else:
                sf2_gain_float_values.append(default_gain_value)
                sf2_file_names_without_parenthesized_gain_expression.append(sf2_file_name_without_extension)
        
        midi_file_path = os.path.join(cwd, midi_folder_name)
        #If there are no MIDI files within the "MIDI Files" 
        #subfolder of the working folder, then an error 
        #message will be displayed on-screen prompting 
        #the user to add some MIDI files to that folder.
        if not os.path.exists(midi_file_path):
            os.mkdir(midi_file_path)
            print(missing_midi_files_string)
            input(press_any_key_string)
            sys.exit(1)
        else:
            #Get a list of ".mid" file names in the "MIDI Files" subfolder of the working folder
            midi_file_names = [file_name for file_name in sorted(os.listdir(midi_file_path)) if file_name[-4:] == ".mid"]
            if midi_file_names == []:
                print(missing_midi_files_string)
                input(press_any_key_string)
                sys.exit(1)
        
        #The previous estimation of the remaining number of seconds is stored in the variable
        #"previous_estimated_seconds" and will be used instead of the current calculation
        #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
        #its estimation.
        previous_estimated_seconds = 0
        first_midi_index = 0
        current_midi_index = first_midi_index
        len_sf2_file_names = len(sf2_file_names)
        len_midi_file_names = len(midi_file_names)
        last_midi_index = (len_sf2_file_names * len_midi_file_names) - 1
        start_time = time.perf_counter()
        
        print("===MIDI-2-FLAC===\n")
        print(f"Now processing your {last_midi_index+1} MIDI files.\n")
        
        #The nested "for" loop will cycle trough every SF2 file that was present 
        #in the "SF2 Files" subfolder of the working folder and then over each 
        #MIDI file found in the "MIDI Files" subfolder in order to render them 
        #to FLAC files with these soundfont files.
        for i in range(len_sf2_file_names):            
            for j in range(len_midi_file_names):
                midi_file_name_without_extension = midi_file_names[j][:-4]
                #The regex pattern for the track number, including dividers 
                #such as hyphens, underscores and plus signs as well as spaces
                #will allow the code to extract the value representing the
                #track number.
                track_number_hits = re.findall(r"[ ]*[\d]+[ ]*[-_+]+[ ]*", midi_file_name_without_extension)
                #If a track number expression was found, the 
                #floating point value will be extracted from it
                if track_number_hits != []:
                    track_number = re.findall(r"[\d]+", track_number_hits[0])[0]
                #If a gain value was found in the SF2 file's name,
                #it will then be stored in the "flac_gain" variable 
                #for use in the FluidSynth subprocess command.
                if sf2_gain_float_values != []:
                    flac_gain = sf2_gain_float_values[i]
                #Otherwise, the default gain value of 0.2 
                #will be used instead.
                else:
                    flac_gain = default_gain_value
                #If there were more than one SF2 files within the "SF2 Files" subfolder of 
                #the working folder, then the SF2 file name (excluding any gain value expressions)
                #will be included as a parenthesized expression at the end of the outputted FLAC
                #file name.
                if len(sf2_file_names_without_parenthesized_gain_expression) > 1:
                    flac_file_name = midi_file_name_without_extension + " (" + sf2_file_names_without_parenthesized_gain_expression[i] + ")"
                    flac_file_output_path = os.path.join(output_flac_files_path, flac_file_name)
                else:
                    flac_file_name = midi_file_name_without_extension
                    flac_file_output_path = os.path.join(output_flac_files_path, flac_file_name)
               
                #The command for the FluidSynth subprocess is made up of the "--fast-render" 
                #option to render MIDI files to raw audio data and store in an output file.
               
                #The default gain of FluidSynth is 0.2, with 
                #possible values spanning 0.0 to 10.0, inclusively,
                #and larger values resulting in louder output.
                #The gain needs to be specified in the file names 
                #of the SF2 files, separated by a hyphen, and must 
                #always be written in floating point format
                #(e.g., "piano - 1.0.sf2"). 
               
                #The -niq flags have the following meaning:
                #n: Don't create a midi driver to read MIDI input events
                #i: Don't read commands from the shell
                #q: Do not print welcome message or other informational output.
                #   On Windows: also suppress all log messages lower than PANIC
                command = f'"{fluidsynth_executable_path}" -niq --sample-rate={sample_rate} -o synth.gain={flac_gain} --fast-render="{flac_file_output_path}.flac" "{os.path.join(sf2_file_path, sf2_file_names[i])}" "{os.path.join(midi_file_path, midi_file_names[j])}"'
                
                #Error messages pertaining to running FluidSynth are only displayed in debug mode
                #(if the user has passed in the "debug" argument when running the code, which 
                #changes the value of "debug_mode" to "True").
                if debug_mode:
                    subprocess.run(command, stdout=subprocess.PIPE)
                else:
                    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
                #A mutagen "File" object is instantiated from the outputted FLAC file.
                track = mutagen.File(f"{flac_file_output_path}.flac")
                #The "delete()" method removes any existing Vorbis comments.
                track.delete()
                #The "title" Vorbis comment derived 
                #from the "flac_file_name" is added.
                track["title"] = flac_file_name
                #If a track number was detected in 
                #the file name, it will be added as 
                #a "tracknumber" Vorbis comment.
                if track_number_hits != []:
                    track["tracknumber"] = track_number 
                #If the user has provided any values in the 
                #"metadata_csv_file.csv" CSV file, then they 
                #will be added in turn as separate Vorbis comments.
                if metadata_dict:
                    for key, value in metadata_dict.items():
                        try:
                            track[key] = value
                        except:
                            pass
        
                #If an album cover image was found in the "Album Cover Image" 
                #subfolder of the working folder, then the following "if" 
                #statement will run.
                if album_cover_image_file_path != "":
                    track.add_picture(album_cover_image)
                
                #The FLAC file's metadata changes are saved. 
                track.save()

                #The function "display_progress" will display the progress string in the console
                #and return the estimated number of seconds for the code to complete.

                #The previous estimation of the remaining number of seconds is stored in the variable
                #"previous_estimated_seconds" and will be used instead of the current calculation
                #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
                #its estimation.
                previous_estimated_seconds = display_progress(current_midi_index, first_midi_index, last_midi_index, start_time, previous_estimated_seconds)
    
                #The value of "current_midi_index" needs to be increment **AFTER** calling 
                #the "display_progress()" function, as the index is zero-indexed and when 
                #calculating the percentage of MIDI files that were rendered, is is then 
                #converted to a one-indexed form in the function.
                current_midi_index += 1
        
        print("\n\n" + textwrap.fill(f"Successfully rendered your MIDI files in the '{output_flac_folder_name}' subfolder!", columns) + "\n")
        input(press_any_key_string)
        
    except Exception as e:
        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
        
        print("\n" + "=" * columns)
        print("CRITICAL ERRROR ENCOUNTERED")
        print("\nDetails:", e)
        print("\n" + "=" * columns)

        #The function "write_entry_in_error_log()" will write 
        #the full technical traceback error to the error log.
        write_entry_in_error_log()

        #Exit with error code
        input(press_any_key_string)
        sys.exit(1)
""")

    with open("README.txt", "w", encoding="utf-8") as f:
            f.write(README_STRING)

    with open("LICENSE.txt", "w", encoding="utf-8") as f:
        f.write(LICENSE_STRING)

    with open("source_code.py", "w", encoding="utf-8") as f:
        f.write(SOURCE_CODE_STRING)

    try:    
        cwd = os.getcwd()

        #The FluidSynth executable will be located 
        #through an "os.walk()" method and its path 
        #will be stored in the "fluidsynth_executable_path"
        #variable.
        fluidsynth_executable_name = "fluidsynth.exe"
        fluidsynth_executable_path = ""
        for root, dirs, files in os.walk(cwd):
            if fluidsynth_executable_name in files:
                fluidsynth_executable_path = os.path.join(root, fluidsynth_executable_name)
        #If the FluidSynth executable could not be located 
        #in the working folder, then an error message will 
        #be printed on-screen.        
        if not fluidsynth_executable_path:
            print("\n" + textwrap.fill("Please include the FluidSynth binary folder in the working folder. As of October 2026, only the FluidSynth versions up to 2.3.0 allow to reliably render MIDI files without appending extra silence to the end of the rendered audio files (see Issue #1408 of the FluidSynth GitHub for more details). You should then select one of these versions from the following link: https://github.com/FluidSynth/fluidsynth/releases.", columns) + "\n")
            input(press_any_key_string)
            sys.exit(1)
 
        #Register the Signal Interrupt (SIGINT) handler that will
        #call the "signal_interrupt_signal_handler()" function 
        #when the user presses on CTRL + C to exit the app.

        #The function "signal_interrupt_signal_handler()" will call
        #"sys.exit(0)" to exit the program normally.
        signal.signal(signal.SIGINT, signal_interrupt_signal_handler)
        
        #For more metadata tags, please consult the following link:
        #https://picard-docs.musicbrainz.org/en/latest/variables/tags_basic.html
        default_csv_file_list = [["album", ""], ["artist", ""], ["comment", ""], ["copyright", ""], ["genre", ""], 
        ["language", ""], ["totaltracks", ""], ["website", ""], ["year", ""]]
        
        csv_folder_path = os.path.join(cwd, metadata_csv_folder_name)
        #If the "Metadata CSV File" subfolder doesn't already exist 
        #in the working folder, then it will be created, and a blank 
        #copy of the default CSV file (without values) will be added 
        #to it.
        if not os.path.exists(csv_folder_path):
            os.mkdir(csv_folder_path)
            #The 'newline=""' argument prevents Windows 
            #from including empty lines between rows.
            with open(os.path.join(csv_folder_path, "metadata_csv_file.csv"), mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter="\t")
                writer.writerows(default_csv_file_list)
        #Otherwise the CSV file names will be collated, and if there is only 
        #one CSV file within the "Metadata CSV File" subfolder, then the 
        #metadata information will be extracted from it.
        else:
            #Get a list of ".csv" file names in the "Metadata CSV File" subfolder of the working folder
            csv_file_names = [file_name for file_name in sorted(os.listdir(csv_folder_path)) if file_name[-4:] == ".csv"]
            #If the has included more than one CSV file in the "Metadata CSV File" subfolder,
            #they will be prompted to only include one such file in that folder.
            if len(csv_file_names) > 1:
                too_many_csv_files_string = "\n" + textwrap.fill(f"Please add a single CSV file in the '{metadata_csv_folder_name}' subfolder of the 'midi2flac' folder and launch the application again. A blank CSV file with no values for the metadata tags will be generated automatically should you delete the {metadata_csv_folder_name}.", width=columns) + "\n"     
                print(too_many_csv_files_string)
                input(press_any_key_string)
                sys.exit(1)
            #If the "Metadata CSV File" subfolder doesn't already contain 
            #a CSV file, then a blank copy of the default CSV file (without values) 
            #will be added to it.
            elif len(csv_file_names) == 0:
                #The 'newline=""' argument prevents Windows 
                #from including empty lines between rows.
                with open(os.path.join(csv_folder_path, "metadata_csv_file.csv"), mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f, delimiter="\t")
                    writer.writerows(default_csv_file_list)
            #Otherwise the CSV file will be opened and the metadata information 
            #for each key will be stored in the "metadata_dict" dictionary, 
            #provided that the stripped value for that key isn't equal to 
            #an empty string, meaning that the user didn't provide a value 
            #there.
            else:
                with open(os.path.join(csv_folder_path, "metadata_csv_file.csv"), mode="r", newline="", encoding="utf-8") as f:
                    reader = csv.reader(f, delimiter="\t")
                    for row in reader:
                        if len(row) > 1 and row[1].strip() != "":
                            metadata_dict[row[0]] = row[1]
                        
        album_cover_image_folder_path = os.path.join(cwd, album_cover_image_folder_name)
        png_file_names = []
        album_cover_image_file_path = ""
        album_cover_image_file_name_without_extension = ""
        mime_value = ""
        #If the "Album Cover Image" subfolder of the working folder 
        #doesn't already exist, then it will be created.
        if not os.path.exists(album_cover_image_folder_path):
            os.mkdir(album_cover_image_folder_path)
        #This "else" statement will first look for any JPEG images within 
        #the "Album Cover Image" subfolder. If none are found, then the 
        #code will look for PNG images instead.
        else:
            #Get a list of ".jpg" file names in the "Album Cover Image" subfolder of the working folder
            jpg_file_names = [file_name for file_name in sorted(os.listdir(album_cover_image_folder_path)) if file_name[-4:] == ".jpg"]
            #If at least one JPEG image was present in the "Album Cover Image",
            #then the "if" statement below will store the first JPEG image's 
            #path in the "album_cover_image_file_path" variable, and the 
            #JPEG file's name in the "album_cover_image_file_name_without_extension"
            #variable (minus the ".jpg" extension). The value of "mime_value" will 
            #then be set to "image/jpeg".
            if jpg_file_names != []:
                album_cover_image_file_path = os.path.join(cwd, album_cover_image_folder_path, jpg_file_names[0])
                album_cover_image_file_name_without_extension = jpg_file_names[0][:-4]
                mime_value = "image/jpeg"
            #A similar approach is taken for PNG image files.
            else:
                #Get a list of ".png" file names in the "Album Cover Image" subfolder of the working folder
                png_file_names = [file_name for file_name in sorted(os.listdir(album_cover_image_folder_path)) if file_name[-4:] == ".png"]
                if png_file_names != []:
                    album_cover_image_file_path = os.path.join(cwd, album_cover_image_folder_path, png_file_names[0]) 
                    album_cover_image_file_name_without_extension = png_file_names[0][:-4]
                    mime_value = "image/png" 

        #If an album cover image was found in the "Album Cover Image" 
        #subfolder of the working folder, then the following "if" 
        #statement will run.
        if album_cover_image_file_path != "":
            #The Boolean variable "has_user_passed_in_image_description_argument",
            #initialized to "False" will be set to "True" should the user have 
            #passed in a cover image description after the "image_description:"
            #argument when running the code. This Boolean variable, when set 
            #to "True" will prevent the code from extracting the cover image 
            #description text form the PNG or JPEG image file name.
            if not has_user_passed_in_image_description_argument:
                cover_image_description = album_cover_image_file_name_without_extension
            
            #The dictionary "img_mode_to_bit_depth_dict" will allow to determine the bit-depth
            #of the cover image using the "Pillow" Python module based on the image mode 
            #(e.g., "1", "L", "P", "RGB" or "RGBA", with a fallback value of 24 bits).
            img_mode_to_bit_depth_dict = {"1": 1, "L": 8, "P": 8, "RGB": 24, "RGBA": 32}
            with Image.open(album_cover_image_file_path) as img:
                
                #For best results, the JPEG or PNG album cover image should meet the following criteria:
                #- File size under 1 MB (ideally under 500 KB)
                #- Resolution of 800x800 or 600x600 pixels. Many devices fail to render images larger than 1024x1024.
                #- The image should be saved in the standard sRGB color space (and not the CMYK color profile, which is meant for printing).
                
                #If the image mode isn't already "RGB" or "RGBA", 
                #then it will be set to "RGB".
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                #If the images are larger in dimension than the value of 
                #"img_dimension_pixel_threshold", they will be downscaled.
                if img.width > img_dimension_pixel_threshold or img_height > img_dimension_pixel_threshold:
                    img.thumbnail((img_dimension_pixel_threshold, img_dimension_pixel_threshold), Image.Resampling.LANCZOS)

                width, height = img.size
                #The dictionary "img_mode_to_bit_depth_dict" will allow to determine the bit-depth
                #of the cover image using the "Pillow" Python module based on the image mode 
                #(e.g., "1", "L", "P", "RGB" or "RGBA", with a fallback value of 24 bits).
                bit_depth = img_mode_to_bit_depth_dict.get(img.mode, 24)
                
                #Compress the image into memory buffer to meet file size restrictions 
                img_buffer = io.BytesIO()
                
                #In the case of JPEGs, start at a quality of 90%
                #and decrease by 5% until the image size meets the 
                #value of "img_size_kilobyte_threshold".
                if mime_value == "image/jpeg":
                    jpg_quality = 90
                    while jpg_quality > 50:
                        #Wipe the memory buffer before another 
                        #iteration of the "while" loop by first 
                        #going back to the very start of the image 
                        #("seek(0)", and then removing everything 
                        #in memory after that point ("truncate()").
                        img_buffer.seek(0)
                        img_buffer.truncate()
                        img.save(img_buffer, format="JPEG", quality=jpg_quality, optimize=True)
                        #If the size of the image in the buffer is smaller or equal to 
                        #the threshold number of kilobytes times 1024 bytes per kilobytes,
                        #then the "while" loop will break.
                        if img_buffer.tell() <= img_size_kilobyte_threshold * 1024:
                            break
                        jpg_quality -= 5                    
                else:
                    #For PNGs, use the maximum compression level, as it is a lossless format
                    img.save(img_buffer, format="PNG", optimize=True, compress_level=9)
                
                #Extract the optimized binary data:
                img_binary_data = img_buffer.getvalue()
            
            #A mutagen "Picture" object is instantiated, and its 
            #attributes are set to the values obtained with the 
            #Pillow Python module.
            album_cover_image = Picture()
            with open(album_cover_image_file_path, "rb") as f:
                album_cover_image.data = img_binary_data
                album_cover_image.type = mutagen.id3.PictureType.COVER_FRONT
                album_cover_image.mime = mime_value
                album_cover_image.desc = cover_image_description
                album_cover_image.width = width
                album_cover_image.height = height
                album_cover_image.depth = bit_depth
         
        #If either the "SF2 Files" subfolder is missing, or if it is empty,
        #it will be created and the code will exit the application while 
        #printing the "missing_sf2_files_string" on-screen.
        missing_sf2_files_string = "\n" + textwrap.fill("Please add the SF2 files in the 'SF2 Files' subfolder of the 'midi2flac' folder and launch the application again.", width=columns) + "\n"     
        
        #If either the "MIDI Files" subfolder is missing, or if it is empty,
        #it will be created and the code will exit the application while 
        #printing the "missing_midi_files_string" on-screen.
        missing_midi_files_string = "\n" + textwrap.fill("Please add the MIDI files in the 'MIDI Files' subfolder of the 'midi2flac' folder and launch the application again.", width=columns) + "\n"     
        
        output_flac_files_path = os.path.join(cwd, output_flac_folder_name)
        if not os.path.exists(output_flac_files_path):
            os.mkdir(output_flac_files_path)
         
        sf2_file_path = os.path.join(cwd, sf2_folder_name)
        if not os.path.exists(sf2_file_path):
            os.mkdir(sf2_file_path)
            print(missing_sf2_files_string)
            input(press_any_key_string)
            sys.exit(1)
        else:
            #Get a list of ".sf2" file names in the "SF2 Files" subfolder of the working folder
            sf2_file_names = [file_name for file_name in sorted(os.listdir(sf2_file_path)) if file_name[-4:] == ".sf2"]
            sf2_file_names_without_parenthesized_gain_expression = []
            sf2_gain_float_values = []
            if sf2_file_names == []:
                print(missing_sf2_files_string)
                input(press_any_key_string)
                sys.exit(1)
        
        #The default gain of FluidSynth is 0.2, with 
        #possible values spanning 0.0 to 10.0, inclusively,
        #and larger values resulting in louder output.
        #The gain needs to be specified in the file names 
        #of the SF2 files, separated by a hyphen, and must 
        #always be written in floating point format
        #(e.g., "piano - 1.0.sf2").
        
        #The regex pattern for the gain expression, including dividers 
        #such as hyphens, underscores and plus signs as well as spaces
        #will allow the code to extract the floating point value representing 
        #the gain setting.
        gain_expression_pattern = r"[ ]*[-_+]*[ ]*[\d]+\.[\d]+[ ]*[-_+]*[ ]*"
        for sf2_file_name in sf2_file_names:
            sf2_file_name_without_extension = sf2_file_name[:-4]
            gain_expression_hits = re.findall(gain_expression_pattern, sf2_file_name_without_extension)
            #If a gain expression was found, the floating point value will be extracted 
            #from it, and then appended to the list of gain values for each SF2 file 
            #("sf2_file_names_without_parenthesized_gain_expression").
            if gain_expression_hits != []:
                sf2_gain_float_values.append(re.findall(r"[\d]+\.[\d]+", gain_expression_hits[0])[0])
                sf2_file_names_without_parenthesized_gain_expression.append(re.sub(gain_expression_pattern, "", sf2_file_name_without_extension))
            else:
                sf2_gain_float_values.append(default_gain_value)
                sf2_file_names_without_parenthesized_gain_expression.append(sf2_file_name_without_extension)
        
        midi_file_path = os.path.join(cwd, midi_folder_name)
        #If there are no MIDI files within the "MIDI Files" 
        #subfolder of the working folder, then an error 
        #message will be displayed on-screen prompting 
        #the user to add some MIDI files to that folder.
        if not os.path.exists(midi_file_path):
            os.mkdir(midi_file_path)
            print(missing_midi_files_string)
            input(press_any_key_string)
            sys.exit(1)
        else:
            #Get a list of ".mid" file names in the "MIDI Files" subfolder of the working folder
            midi_file_names = [file_name for file_name in sorted(os.listdir(midi_file_path)) if file_name[-4:] == ".mid"]
            if midi_file_names == []:
                print(missing_midi_files_string)
                input(press_any_key_string)
                sys.exit(1)
        
        #The previous estimation of the remaining number of seconds is stored in the variable
        #"previous_estimated_seconds" and will be used instead of the current calculation
        #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
        #its estimation.
        previous_estimated_seconds = 0
        first_midi_index = 0
        current_midi_index = first_midi_index
        len_sf2_file_names = len(sf2_file_names)
        len_midi_file_names = len(midi_file_names)
        last_midi_index = (len_sf2_file_names * len_midi_file_names) - 1
        start_time = time.perf_counter()
        
        print("===MIDI-2-FLAC===\n")
        print(f"Now processing your {last_midi_index+1} MIDI files.\n")
        
        #The nested "for" loop will cycle trough every SF2 file that was present 
        #in the "SF2 Files" subfolder of the working folder and then over each 
        #MIDI file found in the "MIDI Files" subfolder in order to render them 
        #to FLAC files with these soundfont files.
        for i in range(len_sf2_file_names):            
            for j in range(len_midi_file_names):
                midi_file_name_without_extension = midi_file_names[j][:-4]
                #The regex pattern for the track number, including dividers 
                #such as hyphens, underscores and plus signs as well as spaces
                #will allow the code to extract the value representing the
                #track number.
                track_number_hits = re.findall(r"[ ]*[\d]+[ ]*[-_+]+[ ]*", midi_file_name_without_extension)
                #If a track number expression was found, the 
                #floating point value will be extracted from it
                if track_number_hits != []:
                    track_number = re.findall(r"[\d]+", track_number_hits[0])[0]
                #If a gain value was found in the SF2 file's name,
                #it will then be stored in the "flac_gain" variable 
                #for use in the FluidSynth subprocess command.
                if sf2_gain_float_values != []:
                    flac_gain = sf2_gain_float_values[i]
                #Otherwise, the default gain value of 0.2 
                #will be used instead.
                else:
                    flac_gain = default_gain_value
                #If there were more than one SF2 files within the "SF2 Files" subfolder of 
                #the working folder, then the SF2 file name (excluding any gain value expressions)
                #will be included as a parenthesized expression at the end of the outputted FLAC
                #file name.
                if len(sf2_file_names_without_parenthesized_gain_expression) > 1:
                    flac_file_name = midi_file_name_without_extension + " (" + sf2_file_names_without_parenthesized_gain_expression[i] + ")"
                    flac_file_output_path = os.path.join(output_flac_files_path, flac_file_name)
                else:
                    flac_file_name = midi_file_name_without_extension
                    flac_file_output_path = os.path.join(output_flac_files_path, flac_file_name)
               
                #The command for the FluidSynth subprocess is made up of the "--fast-render" 
                #option to render MIDI files to raw audio data and store in an output file.
               
                #The default gain of FluidSynth is 0.2, with 
                #possible values spanning 0.0 to 10.0, inclusively,
                #and larger values resulting in louder output.
                #The gain needs to be specified in the file names 
                #of the SF2 files, separated by a hyphen, and must 
                #always be written in floating point format
                #(e.g., "piano - 1.0.sf2"). 
               
                #The -niq flags have the following meaning:
                #n: Don't create a midi driver to read MIDI input events
                #i: Don't read commands from the shell
                #q: Do not print welcome message or other informational output.
                #   On Windows: also suppress all log messages lower than PANIC
                command = f'"{fluidsynth_executable_path}" -niq --sample-rate={sample_rate} -o synth.gain={flac_gain} --fast-render="{flac_file_output_path}.flac" "{os.path.join(sf2_file_path, sf2_file_names[i])}" "{os.path.join(midi_file_path, midi_file_names[j])}"'
                
                #Error messages pertaining to running FluidSynth are only displayed in debug mode
                #(if the user has passed in the "debug" argument when running the code, which 
                #changes the value of "debug_mode" to "True").
                if debug_mode:
                    subprocess.run(command, stdout=subprocess.PIPE)
                else:
                    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
                #A mutagen "File" object is instantiated from the outputted FLAC file.
                track = mutagen.File(f"{flac_file_output_path}.flac")
                #The "delete()" method removes any existing Vorbis comments.
                track.delete()
                #The "title" Vorbis comment derived 
                #from the "flac_file_name" is added.
                track["title"] = flac_file_name
                #If a track number was detected in 
                #the file name, it will be added as 
                #a "tracknumber" Vorbis comment.
                if track_number_hits != []:
                    track["tracknumber"] = track_number 
                #If the user has provided any values in the 
                #"metadata_csv_file.csv" CSV file, then they 
                #will be added in turn as separate Vorbis comments.
                if metadata_dict:
                    for key, value in metadata_dict.items():
                        try:
                            track[key] = value
                        except:
                            pass
        
                #If an album cover image was found in the "Album Cover Image" 
                #subfolder of the working folder, then the following "if" 
                #statement will run.
                if album_cover_image_file_path != "":
                    track.add_picture(album_cover_image)
                
                #The FLAC file's metadata changes are saved. 
                track.save()

                #The function "display_progress" will display the progress string in the console
                #and return the estimated number of seconds for the code to complete.

                #The previous estimation of the remaining number of seconds is stored in the variable
                #"previous_estimated_seconds" and will be used instead of the current calculation
                #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
                #its estimation.
                previous_estimated_seconds = display_progress(current_midi_index, first_midi_index, last_midi_index, start_time, previous_estimated_seconds)
    
                #The value of "current_midi_index" needs to be increment **AFTER** calling 
                #the "display_progress()" function, as the index is zero-indexed and when 
                #calculating the percentage of MIDI files that were rendered, is is then 
                #converted to a one-indexed form in the function.
                current_midi_index += 1
        
        print("\n\n" + textwrap.fill(f"Successfully rendered your MIDI files in the '{output_flac_folder_name}' subfolder!", columns) + "\n")
        input(press_any_key_string)
        
    except Exception as e:
        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
        
        print("\n" + "=" * columns)
        print("CRITICAL ERRROR ENCOUNTERED")
        print("\nDetails:", e)
        print("\n" + "=" * columns)

        #The function "write_entry_in_error_log()" will write 
        #the full technical traceback error to the error log.
        write_entry_in_error_log()

        #Exit with error code
        input(press_any_key_string)
        sys.exit(1)
