#!/usr/bin/env python

import os
import re
import shlex
import shutil
import subprocess
import sys
import traceback

VERBOSE = True

# Compiler
COMPILER   = 'clang++'
CPP_STD    = 'c++14'
STD_LIB    = 'libc++'

# Operating Systems
IOS_MIN_VERSION = '8.0'
OSX_MIN_VERSION = '10.10'

# Architectures
ARCHITECTURES = {
    'ios': ('armv7', 'arm64'),
    'simulator': ('i386', 'x86_64'),
    'osx': ('i386', 'x86_64')
}

BOOST_VERSION  = '1.60.0'
BOOST_LIBS     = ['chrono', 'thread', 'system']
BOOST_HEADERS  = [
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
    ]

BOOST_TARBALL_URL_TEMPLATE = 'http://sourceforge.net/projects/boost/files/boost/{}/boost_{}.tar.bz2/download'

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

class BuildEnv:
    def __init__(self, root):
        self.root = root
        self.dir_stack = []
        self.xcode_root = shell_output('xcode-select -print-path')
        self.ios_sdk_version = shell_output('xcrun -sdk iphoneos --show-sdk-version')
        self.osx_sdk_version = shell_output('xcrun -sdk macosx --show-sdk-version')
        self.ios_simulator_root = os.path.join(self.xcode_root, 'Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator{}.sdk'.format(self.ios_sdk_version))

    def resolve_path(self, relative_path):
        return os.path.join(self.root, relative_path)

    def make_dir(self, relative_path):
        path = self.resolve_path(relative_path)
        if not os.path.isdir(path):
            print 'Creating {}'.format(path)
            os.makedirs(path)
        return path

    def prepare(self):
        self.make_dir('')

    def clean(self):
        print 'Cleaning up {}'.format(self.root)
        if (os.path.isdir(self.root)):
            shutil.rmtree(self.root)

    def cd(self, path):
        print 'cd {}'.format(path)
        os.chdir(path)

    def push_dir(self, relative_path):
        self.dir_stack.append(os.getcwd())
        self.cd(self.resolve_path(relative_path))

    def pop_dir(self):
        if len(self.dir_stack) > 0:
            directory = self.dir_stack.pop()
            self.cd(directory)

class BoostSource:
    def __init__(self, build_env, version):
        self.build_env = build_env
        self.version = version
        self.version_underscore = '_'.join(self.version.split('.'))
        self.root = self.build_env.resolve_path('boost_{}'.format(self.version_underscore))
        self.tarball_url = BOOST_TARBALL_URL_TEMPLATE.format(self.version, self.version_underscore)
        self.tarball_path = os.path.join(self.build_env.root, 'boost_{}.tar.bz2'.format(self.version_underscore))
        self.config_path = os.path.join(self.root, 'user-config.jam')

    def resolve_path(self, relative_path):
        return os.path.join(self.root, relative_path)

    def download(self):
        if os.path.isfile(self.tarball_path):
            print 'Found Boost {} tarball: {}'.format(self.version, self.tarball_path)
        else:
            print 'Downloading Boost {} tarball: {}'.format(self.version, self.tarball_path)
            shell('curl -L -o {} {}'.format(self.tarball_path, self.tarball_url))

    def unpack(self):
        if not os.path.isfile(self.tarball_path):
            print 'Boost {} tarball not found: {}'.format(self.version, self.tarball_path)
        if os.path.isdir(self.root):
            print 'Found Boost {} source: {}'.format(self.version, self.root)
        else:
            self.build_env.make_dir(self.root)
            self.build_env.push_dir(self.build_env.root)
            print 'Unpacking Boost {} tarball in {}'.format(self.version, self.build_env.root)
            shell('tar xfj {}'.format(self.tarball_path))
            self.build_env.pop_dir()

    # These files are missing in the ARM iPhoneOS SDK, but they are in the simulator.
    # They are supported on the device, so we copy them from x86 SDK to a staging area
    # to use them on ARM, too.
    def invent_missing_headers(self):
        simulator_include = os.path.join(self.build_env.ios_simulator_root, 'usr/include')
        for filename in ['crt_externs.h', 'bzlib.h']:
            filepath = os.path.join(simulator_include, filename)
            if not os.path.isfile(filepath):
                print 'File doesn\'t exist: {}'.format(filepath)
                sys.exit(1)
            dst_path = self.resolve_path(filename)
            if not os.path.isfile(dst_path):
                print 'Copying {}'.format(filename)
                shutil.copyfile(filepath, dst_path)

    def bootstrap(self):
        self.build_env.push_dir(self.root)
        print 'Bootstrapping Boost {} with {}'.format(self.version, ', '.join(BOOST_LIBS))
        shell('./bootstrap.sh --with-libraries={}'.format(','.join(BOOST_LIBS)))
        self.build_env.pop_dir()

    def config_contents(self):
        return """
using darwin : {ios_sdk_version}~iphone
: {xcode_root}/Toolchains/XcodeDefault.xctoolchain/usr/bin/{compiler} -arch armv7 -arch arm64 "-isysroot {xcode_root}/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS{ios_sdk_version}.sdk" -I{xcode_root}/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS{ios_sdk_version}.sdk/usr/include
: <striper> <root>{xcode_root}/Platforms/iPhoneOS.platform/Developer
: <architecture>arm <target-os>iphone
;
using darwin : {ios_sdk_version}~iphonesim
: {xcode_root}/Toolchains/XcodeDefault.xctoolchain/usr/bin/{compiler} -arch i386 -arch x86_64 "-isysroot {xcode_root}/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator{ios_sdk_version}.sdk" -I{xcode_root}/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator{ios_sdk_version}.sdk/usr/include
: <striper> <root>{xcode_root}/Platforms/iPhoneSimulator.platform/Developer
: <architecture>x86 <target-os>iphone
;
using darwin : {osx_sdk_version}~osx
: {xcode_root}/Toolchains/XcodeDefault.xctoolchain/usr/bin/{compiler} -arch i386 -arch x86_64 "-isysroot {xcode_root}/Platforms/MacOSX.platform/Developer/SDKs/MacOSX{osx_sdk_version}.sdk" -I{xcode_root}/Platforms/MacOSX.platform/Developer/SDKs/MacOSX{osx_sdk_version}.sdk/usr/include
: <striper> <root>{xcode_root}/Platforms/MacOSX.platform/Developer
: <architecture>x86 <target-os>darwin
;
        """.format(xcode_root=self.build_env.xcode_root,
                   compiler=COMPILER,
                   ios_sdk_version=self.build_env.ios_sdk_version,
                   osx_sdk_version=self.build_env.osx_sdk_version)

    def create_config(self):
        if not os.path.isfile(self.config_path):
            template_path = os.path.join(self.root, 'tools/build/example/user-config.jam')
            if not os.path.isfile(template_path):
                print 'File doesn\'t exist: {}'.format(template_path)
                sys.exit(1)
            shutil.copyfile(template_path, self.config_path)
            with open(self.config_path, 'a') as f:
                f.write(self.config_contents())

    def setup(self):
        self.download()
        self.unpack()
        self.invent_missing_headers()
        self.bootstrap()
        self.create_config()

class BuildTask:
    def __init__(self, build_env, boost_source, platform, target='stage'):
        self.build_env = build_env
        self.boost_source = boost_source
        self.platform = platform
        self.target = target
        self.relative_build_dir = '{}-build'.format(platform)
        self.build_dir = self.boost_source.resolve_path(self.relative_build_dir)
        self.relative_stage_dir = os.path.join(self.relative_build_dir, 'stage')
        self.stage_dir = self.boost_source.resolve_path(self.relative_stage_dir)
        self.relative_prefix_dir = os.path.join(self.relative_build_dir, 'prefix')
        self.prefix_dir = self.boost_source.resolve_path(self.relative_prefix_dir)

    def common_build_args(self):
        return [
            '-j16',
            '--build-dir={}'.format(self.relative_build_dir),
            '--stage-dir={}'.format(self.relative_stage_dir),
            '--prefix={}'.format(self.relative_prefix_dir),
            'linkflags="-stdlib={}"'.format(STD_LIB),
            'link=static',
            'variant=release',
            '-sBOOST_BUILD_USER_CONFIG={}'.format(self.boost_source.config_path),
            ]

    def ios_and_simulator_build_args(self):
        return [
            'target-os=iphone',
            ]

    def ios_build_args(self):
        return [
            'macosx-version=iphone-{}'.format(self.build_env.ios_sdk_version),
            'toolset=darwin-{}~iphone'.format(self.build_env.ios_sdk_version),
            'define=_LITTLE_ENDIAN',
            'architecture=arm',
            ]

    def simulator_build_args(self):
        return [
            'macosx-version=iphonesim-{}'.format(self.build_env.ios_sdk_version),
            'toolset=darwin-{}~iphonesim'.format(self.build_env.ios_sdk_version),
            'architecture=x86',
            ]

    def osx_build_args(self):
        return [
            'target-os=darwin',
            'macosx-version={}'.format(self.build_env.osx_sdk_version),
            'toolset=darwin-{}~osx'.format(self.build_env.osx_sdk_version),
            'architecture=x86',
            ]

    def common_cpp_flags(self):
        return [
            '-std={}'.format(CPP_STD),
            '-stdlib={}'.format(STD_LIB),
            '-fvisibility=hidden',
            '-fvisibility-inlines-hidden',
            '-fPIC', 
            '-DBOOST_SP_USE_SPINLOCK',
            ]

    def ios_and_simulator_cpp_flags(self):
        return [
            '-miphoneos-version-min={}'.format(IOS_MIN_VERSION),
            '-fembed-bitcode',
            ]

    def osx_cpp_flags(self):
        return [
            '-mmacosx-version-min={}'.format(OSX_MIN_VERSION),
            ]

    def cpp_flags(self):
        flags = self.common_cpp_flags()
        if self.platform in ('ios', 'simulator'):
            flags.extend(self.ios_and_simulator_cpp_flags())
        elif self.platform == 'osx':
            flags.extend(self.osx_cpp_flags())
        else:
            print 'Unexpected platform: {}'.format(self.platform)
            sys.exit(1)
        return flags

    def build_args(self):
        args = self.common_build_args()
        if self.platform in ('ios', 'simulator'):
            args.extend(self.ios_and_simulator_build_args())
            if self.platform == 'ios':
                args.extend(self.ios_build_args())
            else:
                args.extend(self.simulator_build_args())
        elif self.platform == 'osx':
            args.extend(self.osx_build_args())
        else:
            print 'Unexpected platform: {}'.format(self.platform)
            sys.exit(1)
        flags = self.cpp_flags()
        if flags and len(flags) > 0:
            args.append('cxxflags="{}"'.format(' '.join(flags)))
        args.append(self.target)
        return args

    def run(self):
        self.build_env.push_dir(self.boost_source.root)
        print 'Running {} target on {}'.format(self.target, self.platform)
        shell('./b2 {}'.format(' '.join(self.build_args())))
        self.build_env.pop_dir()

def prepare():
    make_dir(OUTPUT_DIR_LIB)
    shutil.copyfile(BOOST_CONFIG_FILE, USER_CONFIG_FILE)
    with open(USER_CONFIG_FILE, 'a') as f:
        f.write(USER_CONFIG_FILE_CONTENTS)

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

if __name__ == '__main__': 
    
    # Prepare the build folder
    build_env = BuildEnv(os.path.join(os.getcwd(), 'build'))
    build_env.prepare()

    # Download and unpack the boost source
    boost_source = BoostSource(build_env, BOOST_VERSION)
    boost_source.setup()

    # Define the targets for each platform
    tasks = {
        "ios": ['stage', 'install'],
        "simulator": ['stage'],
        "osx": ['stage'],
    }
    platforms = tasks.keys()

    # Build each platform's targets
    for platform in platforms:
        for target in tasks[platform]:
            build_task = BuildTask(build_env, boost_source, platform, target)
            build_task.run()

    # Package and install
    # package()
    # bcp()

    # Remove build artifacts
    # clean()
