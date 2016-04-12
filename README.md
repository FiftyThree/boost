This is a mirror of the Boost source we use at FiftyThree, including pre-built static libraries for iOS and OS X containing the following Boost libraries:
* Boost.Thread
* Boost.Chrono
* Boost.System

The `include/boost` directory contains all the headers for these non header-only libraries, as well as the header-only dependencies for the modules and files listed at the top of the `build.py` script.

The fat lib `lib/ios/libboost.a` contains the libraries listed above, compiled for **armv7** and **arm64**, as well as **i386** and **x86_64** for simulator compatibility. These were compiled with **bitcode enabled** and a minimum iOS version of **8.0** by the **iPhoneOS9.3.sdk** and **iPhoneSimulator9.3.sdk**.

The fat lib `lib/osx/libboost.a` contains the libraries listed above, compiled for **i386** and **x86_64**. These were compiled with a minimum OS X version of **10.9** by the **MacOSX10.11sdk**.
