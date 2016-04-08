#!/usr/bin/env python

import os
import re
import shlex
import shutil
import subprocess
import sys
import traceback

VERBOSE = False

BOOST_LIBS     = ('chrono', 'thread', 'system')
BOOST_HEADERS  = (
    'algorithm',
    'any',
    'exception',
    'iostreams',
    'optional',
    'typeof',
    'variant',
    'boost/circular_buffer.hpp',
    'boost/container/flat_map.hpp',
    'boost/container/flat_set.hpp',
    'boost/scope_exit.hpp',
    'boost/uuid/sha1.hpp'
    )

#-------------------------------------------------------------------------------
#
# Shell utilities
#
#-------------------------------------------------------------------------------

# There are various flavors of these commands.
#
# Description of each command:
#
#  Command       Arguments      Output
#  -------       -------------  ------------------------------------------------
#  shell         cmd            To stdout/stderr, returns status code
#  shell_pipe    callback, cmd  Each line invokes `callback(line)`, returns status
#
# shell will by default halt the build if the command returns
# a non-zero exit code. Use the ignore_failure parameter to prevent this.

def message_cmd(cmd_long, msg):
    cmd = os.path.split(shlex.split(cmd_long)[0])[-1]
    if cmd in ('sh', 'bash'):
        cmd = os.path.split(shlex.split(cmd_long)[1])[-1]
        if cmd == '-x':
            cmd = os.path.split(shlex.split(cmd_long)[2])[-1]
    print '{}| {}'.format(cmd, msg)

class EchoAccumFilter:
    def __init__(self, cmd):
        self.command = cmd
        self.data = []

    def handle_line_silent(self, line):
        self.data.append(line)

    def get_data(self):
        return ''.join(self.data)

def shell_output(cmd, ignore_failure = False):
    filt = EchoAccumFilter(cmd)
    status = shell_pipe(filt.handle_line_silent, cmd)
    if status != 0 and not ignore_failure:
        print '{} failed with status {}'.format(cmd, status)
        sys.exit(1)
    return filt.get_data().rstrip()

def shell(cmd, ignore_failure = False):
    # Print out every line of the command's output, with a prefix of the command executable's name.
    callback = lambda x: [message_cmd(cmd, y.rstrip()) for y in re.split('\n|\r', x) if y.strip() != ''] if VERBOSE else None
    status = shell_pipe(callback, cmd)
    if status != 0 and not ignore_failure:
        print '{} failed with status {}'.format(cmd, status)
        sys.exit(1)

def shell_pipe(callback, cmd, redirect_stderr_to_stdout = True):
    stdout = subprocess.PIPE
    if redirect_stderr_to_stdout:
        stderr = subprocess.STDOUT
    else:
        stderr = None

    process = subprocess.Popen(shlex.split(cmd), shell = False, stdout = stdout, stderr = stderr)

    while process.poll() == None:
        line = process.stdout.readline()
        if not line:
            break
        if callback:
            callback(line)

    process.wait()

    while True:
        line = process.stdout.readline()
        if not line:
            break
        if callback:
            callback(line)

    return process.returncode

#-------------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------------

IOS_MIN_VERSION            = '8.0'
XCODE_ROOT                 = shell_output('xcode-select -print-path')
IOS_SDK_VERSION            = shell_output('xcrun -sdk iphoneos --show-sdk-version')
OSX_SDK_VERSION            = shell_output('xcrun -sdk macosx --show-sdk-version')
IOS_SIMULATOR_ROOT         = os.path.join(XCODE_ROOT, 'Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator{}.sdk'.format(IOS_SDK_VERSION))
ARCHITECTURES              = ('armv7', 'arm64', 'i386', 'x86_64')

BUILD_DIR                  = os.path.join(os.getcwd(), 'build')

BOOST_VERSION_PERIOD       = '1.60.0'
BOOST_VERSION_UNDERSCORE   = '1_60_0'
BOOST_TARBALL_PATH         = os.path.join(BUILD_DIR, 'boost_{}.tar.bz2'.format(BOOST_VERSION_UNDERSCORE))
BOOST_TARBALL_URL          = 'http://sourceforge.net/projects/boost/files/boost/{}/boost_{}.tar.bz2/download'.format(BOOST_VERSION_PERIOD, BOOST_VERSION_UNDERSCORE)
BOOST_ROOT                 = os.path.join(BUILD_DIR, 'boost_{}'.format(BOOST_VERSION_UNDERSCORE))
BOOST_INCLUDE_DIR          = os.path.join(BOOST_ROOT, 'boost')

OUTPUT_DIR                 = os.getcwd()
OUTPUT_DIR_SRC             = os.path.join(OUTPUT_DIR, 'include/boost')
OUTPUT_DIR_LIB             = os.path.join(OUTPUT_DIR, 'lib')

BUILD_SRC_DIR              = os.path.join(BUILD_DIR, 'src')
BUILD_IOS_LIB_DIR          = os.path.join(BUILD_DIR, 'libs/boost/lib')
BUILD_IOS_INCLUDE_DIR      = os.path.join(BUILD_DIR, 'libs/boost/include/boost')
BUILD_IOS_PREFIX_DIR       = os.path.join(BUILD_DIR, 'ios/prefix')

COMPILER                   = 'clang++'
CPP_STD                    = 'c++14'
STD_LIB                    = 'libc++'
NUM_THREADS                = 16
CPP_FLAGS                  = ' '.join((
                            '-fPIC', 
                            '-DBOOST_SP_USE_SPINLOCK',
                            '-std={}'.format(CPP_STD),
                            '-stdlib={}'.format(STD_LIB),
                            '-miphoneos-version-min={}'.format(IOS_MIN_VERSION),
                            '-fembed-bitcode',
                            '-fvisibility=hidden',
                            '-fvisibility-inlines-hidden'
                            ))
CROSS_TOP_IOS              = '{}/Platforms/iPhoneOS.platform/Developer'.format(XCODE_ROOT)
CROSS_SDK_IOS              = 'iPhoneOS{}.sdk'.format(IOS_SDK_VERSION)
CROSS_TOP_SIM              = '{}/Platforms/iPhoneSimulator.platform/Developer'.format(XCODE_ROOT)
CROSS_SDK_SIM              = 'iPhoneSimulator{}.sdk'.format(IOS_SDK_VERSION)

BOOST_CONFIG_FILE          = os.path.join(BOOST_ROOT, 'tools/build/example/user-config.jam')
USER_CONFIG_FILE           = os.path.join(BOOST_ROOT, 'user-config.jam')
USER_CONFIG_FILE_CONTENTS  = """using darwin : {ios_sdk_version}~iphone
: {xcode_root}/Toolchains/XcodeDefault.xctoolchain/usr/bin/{compiler} -arch armv7 -arch arm64 {cpp_flags} "-isysroot {cross_top_ios}/SDKs/{cross_sdk_ios}" -I{cross_top_ios}/SDKs/{cross_sdk_ios}/usr/include/
: <striper> <root>{xcode_root}/Platforms/iPhoneOS.platform/Developer
: <architecture>arm <target-os>iphone
;
using darwin : {ios_sdk_version}~iphonesim
: {xcode_root}/Toolchains/XcodeDefault.xctoolchain/usr/bin/{compiler} -arch i386 -arch x86_64 {cpp_flags} "-isysroot {cross_top_sim}/SDKs/{cross_sdk_sim}" -I{cross_top_sim}/SDKs/{cross_sdk_sim}/usr/include/
: <striper> <root>{xcode_root}/Platforms/iPhoneSimulator.platform/Developer
: <architecture>x86 <target-os>iphone
;
""".format(compiler=COMPILER,
           ios_sdk_version=IOS_SDK_VERSION, 
           xcode_root=XCODE_ROOT,
           cross_top_ios=CROSS_TOP_IOS,
           cross_sdk_ios=CROSS_SDK_IOS,
           cross_top_sim=CROSS_TOP_SIM,
           cross_sdk_sim=CROSS_SDK_SIM,
           cpp_flags=CPP_FLAGS)

#-------------------------------------------------------------------------------
#
# Boost
#
#-------------------------------------------------------------------------------

def clean():
    print 'Cleaning up {}'.format(BUILD_DIR)
    if (os.path.isdir(BUILD_DIR)):
        shutil.rmtree(BUILD_DIR)

def download_boost_tarball():
    if (os.path.isfile(BOOST_TARBALL_PATH)):
        print 'Found Boost {} tarball: {}'.format(BOOST_VERSION_PERIOD, BOOST_TARBALL_PATH)
    else:
        print 'Downloading Boost {} tarball: {}'.format(BOOST_VERSION_PERIOD, BOOST_TARBALL_PATH)
        shell('curl -L -o {} {}'.format(BOOST_TARBALL_PATH, BOOST_TARBALL_URL))

def unpack_boost_tarball():
    print 'Unpacking tarball in {}'.format(BOOST_ROOT)
    cwd = os.getcwd()
    os.chdir(BUILD_DIR)
    shell('tar xfj {}'.format(BOOST_TARBALL_PATH))
    os.chdir(cwd)

def invent_missing_headers():
    # These files are missing in the ARM iPhoneOS SDK, but they are in the simulator.
    # They are supported on the device, so we copy them from x86 SDK to a staging area
    # to use them on ARM, too.
    include_dir = os.path.join(IOS_SIMULATOR_ROOT, 'usr/include')
    for filename in ['crt_externs.h', 'bzlib.h']:
        filepath = os.path.join(include_dir, filename)
        if not os.path.isfile(filepath):
            print 'File doesn\'t exist: {}'.format(filepath)
            sys.exit(1)
        print 'Copying {} to {}'.format(filepath, os.path.join(BOOST_ROOT, filename))
        shutil.copyfile(filepath, os.path.join(BOOST_ROOT, filename))

def make_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)

def prepare():
    make_dir(OUTPUT_DIR_LIB)
    shutil.copyfile(BOOST_CONFIG_FILE, USER_CONFIG_FILE)
    with open(USER_CONFIG_FILE, 'a') as f:
        f.write(USER_CONFIG_FILE_CONTENTS)

def bootstrap():
    cwd = os.getcwd()
    os.chdir(BOOST_ROOT)

    print 'Bootstrapping with {}'.format(', '.join(BOOST_LIBS))
    shell('./bootstrap.sh --with-libraries={}'.format(','.join(BOOST_LIBS)))

    os.chdir(cwd)

def build_args(platform, phase):
    return (
        '-j{}'.format(NUM_THREADS),
        '--build-dir={}-build'.format(platform),
        '-sBOOST_BUILD_USER_CONFIG={}'.format(USER_CONFIG_FILE),
        '--stagedir={}-build/stage'.format(platform),
        ('--prefix={}'.format(BUILD_IOS_PREFIX_DIR) if platform == 'iphone' else ''),
        '--toolset=darwin-{}~{}'.format(IOS_SDK_VERSION, platform),
        'cxxflags="-miphoneos-version-min={} -stdlib={} -fembed-bitcode"'.format(IOS_MIN_VERSION, STD_LIB),
        'variant=release',
        'linkflags="-stdlib={}"'.format(STD_LIB),
        'architecture={}'.format('arm' if platform == 'iphone' else 'x86'),
        'target-os=iphone',
        'macosx-version={}-{}'.format(platform, IOS_SDK_VERSION),
        ('define=_LITTLE_ENDIAN' if platform == 'iphone' else ''),
        'link=static',
        phase
        )

def platform_for_arch(arch):
    if arch in ('armv7', 'arm64'):
        return 'iphone'
    elif arch in ('i386', 'x86_64'):
        return 'iphonesim'
    else:
        print 'Invalid architecture: {}'.format(arch)
        sys.exit(1)

def sdk_for_platform(platform):
    if platform == 'iphone':
        return 'iphoneos'
    elif platform == 'iphonesim':
        return 'iphonesimulator'
    else:
        print 'Invalid platform: {}'.format(platform)
        sys.exit(1)        

def build():
    cwd = os.getcwd()
    os.chdir(BOOST_ROOT)

    print 'Running bjam for iphone-build stage'
    shell('./bjam {}'.format(' '.join(build_args('iphone', 'stage'))))

    print 'Running bjam for iphone-build install'
    shell('./bjam {}'.format(' '.join(build_args('iphone', 'install'))))

    print 'Running bjam for iphonesim-build stage'
    shell('./bjam {}'.format(' '.join(build_args('iphonesim', 'stage'))))

    os.chdir(cwd)    

def package():
    cwd = os.getcwd()
    os.chdir(BOOST_ROOT)

    for arch in ARCHITECTURES:
        make_dir(os.path.join(BUILD_IOS_LIB_DIR, '{}/obj'.format(arch)))

    lib_dir = 'iphone-build/stage/lib'
    libs = [lib for lib in os.listdir(lib_dir) if os.path.isfile(os.path.join(lib_dir, lib))]
    
    for lib in libs:
        for arch in ARCHITECTURES:
            inner_cwd = os.getcwd()
            command = 'lipo "{platform}-build/stage/lib/{name}" -thin {arch} -o "{build_dir}/{arch}/{name}"'.format(platform=platform_for_arch(arch), name=lib, arch=arch, build_dir=BUILD_IOS_LIB_DIR)
            shell('xcrun --sdk {} {}'.format('iphoneos', command))
            os.chdir('{}/{}/obj'.format(BUILD_IOS_LIB_DIR, arch))
            shell('ar -x ../{}'.format(lib))
            os.chdir(inner_cwd)

    print 'Collecting architecture-specific products'
    boost_libs = []
    for arch in ARCHITECTURES:
        inner_cwd = os.getcwd()
        os.chdir('{}/{}'.format(BUILD_IOS_LIB_DIR, arch))
        if os.path.isfile('libboost.a'):
            os.remove('libboost.a')
        obj_dir = os.path.join(os.getcwd(), 'obj')
        obj_files = [os.path.join(obj_dir, obj) for obj in os.listdir('obj') if os.path.isfile(os.path.join(obj_dir, obj)) and obj.endswith('.o')]
        command = 'ar crus libboost.a {}'.format(' '.join(obj_files))
        shell('xcrun --sdk {} {}'.format(sdk_for_platform(platform_for_arch(arch)), command))
        boost_libs.append(os.path.join(os.getcwd(), 'libboost.a'))
        os.chdir(inner_cwd)

    print 'Creating the fat lib at {}/libboost.a'.format(OUTPUT_DIR_LIB)
    shell('lipo -c {} -output {}/libboost.a'.format(' '.join(boost_libs), OUTPUT_DIR_LIB))

    os.chdir(cwd)

def bcp():
    cwd = os.getcwd()
    os.chdir(BOOST_ROOT)

    bcp_path = os.path.join(BOOST_ROOT, 'dist/bin/bcp')
    if not os.path.isfile(bcp_path):
        print 'Building bcp'
        shell('./b2 tools/bcp')
        if not os.path.isfile(bcp_path):
            print 'Unable to build bcp'
            sys.exit(1)

    tmp_dir = os.path.join(BOOST_ROOT, 'tmp')
    make_dir(tmp_dir)
    print 'Extracting {}'.format(' '.join(BOOST_LIBS + BOOST_HEADERS))
    shell('{} {} {}'.format(bcp_path, ' '.join(BOOST_LIBS + BOOST_HEADERS), tmp_dir))

    if os.path.isdir(OUTPUT_DIR_SRC):
        shutil.rmtree(OUTPUT_DIR_SRC)
    print 'Installing headers in {}'.format(OUTPUT_DIR_SRC)
    shutil.copytree(os.path.join(tmp_dir, 'boost'), OUTPUT_DIR_SRC)

    os.chdir(cwd)

#-------------------------------------------------------------------------------
#
# Main
#
#-------------------------------------------------------------------------------

def main():

    # Remove any old build artifacts
    clean()

    # Prepare the build folder
    make_dir(BUILD_DIR)

    # Download and unpack
    download_boost_tarball()
    unpack_boost_tarball()
    invent_missing_headers()

    # Configure and build
    prepare()
    bootstrap()
    build()

    # Package and install
    package()
    bcp()

    # Remove build artifacts
    clean()

if __name__ == '__main__': 
    main()