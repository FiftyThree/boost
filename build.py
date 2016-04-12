#!/usr/bin/env python

import os
import re
import shlex
import shutil
import subprocess
import sys
import traceback

VERBOSE = False

# Compiler
COMPILER   = 'clang++'
CPP_STD    = 'c++14'
STD_LIB    = 'libc++'

# Operating Systems
IOS_MIN_VERSION = '8.0'
OSX_MIN_VERSION = '10.9'

# Platforms
PLATFORMS = ['ios', 'simulator', 'osx']

# Architectures
ARCHITECTURES = {
    'ios': ['armv7', 'arm64'],
    'simulator': ['i386', 'x86_64'],
    'osx': ['i386', 'x86_64'],
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
# Boost
#
#-------------------------------------------------------------------------------

class BuildEnv:

    def __init__(self, root):
        self.root = os.path.join(root, 'build')
        self.dir_stack = []
        self.xcode_root = shell_output('xcode-select -print-path')
        self.ios_sdk_version = shell_output('xcrun -sdk iphoneos --show-sdk-version')
        self.osx_sdk_version = shell_output('xcrun -sdk macosx --show-sdk-version')
        self.ios_simulator_root = os.path.join(self.xcode_root, 'Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator{}.sdk'.format(self.ios_sdk_version))
        self.output_lib_dir = os.path.join(root, 'lib')
        self.output_src_dir = os.path.join(root, 'include/boost')

    def resolve_path(self, relative_path):
        return os.path.join(self.root, relative_path)

    def make_dir(self, relative_path):
        path = self.resolve_path(relative_path)
        if not os.path.isdir(path):
            if VERBOSE:
                print 'Creating {}'.format(path)
            os.makedirs(path)
        return path

    def prepare(self):
        self.make_dir('')

    def cleanup(self):
        print 'Cleaning up {}'.format(self.root)
        if (os.path.isdir(self.root)):
            shutil.rmtree(self.root)

    def cd(self, path):
        if VERBOSE:
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
            '--stagedir={}'.format(self.relative_stage_dir),
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

class Packager:

    def __init__(self, build_env, boost_source):
        self.build_env = build_env
        self.boost_source = boost_source
        self.output_lib_dir = self.build_env.resolve_path('lib')
        self.ios_lib_dir = os.path.join(self.output_lib_dir, 'ios')
        self.osx_lib_dir = os.path.join(self.output_lib_dir, 'osx')
        self.lib_name = 'libboost.a'

    def get_libs(self):
        self.build_env.push_dir(self.boost_source.root)
        lib_dirs = list()
        for platform in PLATFORMS:
            build_task = BuildTask(self.build_env, self.boost_source, platform)
            lib_dirs.append(os.path.join(build_task.relative_stage_dir, 'lib'))
        all_libs = set()
        for lib_dir in lib_dirs:
            libs = [lib for lib in os.listdir(lib_dir) if os.path.isfile(os.path.join(lib_dir, lib))]
            all_libs.update(set(libs))
        self.build_env.pop_dir()
        return list(all_libs)

    def separate_architectures(self, all_libs):
        self.build_env.push_dir(self.boost_source.root)
        for platform in PLATFORMS:
            build_task = BuildTask(self.build_env, self.boost_source, platform)
            input_dir = os.path.join(build_task.relative_stage_dir, 'lib')
            output_dir = self.ios_lib_dir if platform in ['ios', 'simulator'] else self.osx_lib_dir
            sdk = 'iphoneos' if platform in ['ios', 'simulator'] else 'macosx'
            self.build_env.make_dir(output_dir)
            for lib in all_libs:
                input_path = os.path.join(input_dir, lib)
                if os.path.isfile(input_path):
                    for arch in ARCHITECTURES[platform]:
                        arch_dir = os.path.join(output_dir, arch)
                        self.build_env.make_dir(arch_dir)
                        # Split the fat libs into their architecture-specific libs
                        output_path = os.path.join(arch_dir, lib)
                        lipo_command = 'lipo "{}" -thin {} -o "{}"'.format(input_path, arch, output_path)
                        shell('xcrun --sdk {} {}'.format(sdk, lipo_command))
                        # Decompose the architecture-specific libs
                        obj_dir = os.path.join(arch_dir, 'obj')
                        self.build_env.make_dir(obj_dir)
                        self.build_env.push_dir(obj_dir)
                        shell('ar -x ../{}'.format(lib))
                        obj_files = [obj_file for obj_file in os.listdir('./') if os.path.isfile(obj_file) and obj_file.endswith('.o')]
                        self.build_env.pop_dir()
                        # Create an architecture-specific fat lib
                        self.build_env.push_dir(arch_dir)
                        if os.path.isfile(self.lib_name):
                            os.remove(self.lib_name)
                        ar_command = 'ar crus {} {}'.format(self.lib_name, ' '.join([os.path.join('obj', obj_file) for obj_file in obj_files]))
                        shell('xcrun --sdk {} {}'.format(sdk, ar_command))
                        self.build_env.pop_dir()
        self.build_env.pop_dir()

    def create_fat_libs(self):
        for platform_dir in [self.ios_lib_dir, self.osx_lib_dir]:
            self.build_env.push_dir(platform_dir)
            arch_libs = []
            for arch_dir in [arch_dir for arch_dir in os.listdir('./') if os.path.isdir(arch_dir)]:
                arch_lib = os.path.join(arch_dir, self.lib_name)
                if os.path.isfile(arch_lib):
                    arch_libs.append(arch_lib)
            if os.path.isfile(self.lib_name):
                os.remove(self.lib_name)
            shell('lipo -c {} -output {}'.format(' '.join(arch_libs), self.lib_name))
            self.build_env.pop_dir()

    def install(self):
        self.build_env.push_dir(self.build_env.root)
        for platform_dir in [self.ios_lib_dir, self.osx_lib_dir]:
            fat_lib_path = os.path.join(platform_dir, self.lib_name)
            relative_fat_lib_path = os.path.relpath(fat_lib_path, self.output_lib_dir)
            install_path = os.path.join(self.build_env.output_lib_dir, relative_fat_lib_path)
            self.build_env.make_dir(os.path.dirname(install_path))
            shutil.copyfile(fat_lib_path, install_path)
        self.build_env.pop_dir()

    def run(self):
        all_libs = self.get_libs()
        self.separate_architectures(all_libs)
        self.create_fat_libs()
        self.install()

class Headers:

    def __init__(self, build_env, boost_source):
        self.build_env = build_env
        self.boost_source = boost_source
        self.bcp_path = self.boost_source.resolve_path('dist/bin/bcp')
        self.output_src_dir = self.build_env.resolve_path('src')

    def build_bcp(self):
        if os.path.isfile(self.bcp_path):
            print 'Found bcp: {}'.format(self.bcp_path)
        else:
            self.build_env.push_dir(self.boost_source.root)
            print 'Building bcp'
            shell('./b2 tools/bcp')
            self.build_env.pop_dir()
        if not os.path.isfile(self.bcp_path):
            print 'Unable to build bcp'
            sys.exit(1)

    def extract_headers(self):
        self.build_env.push_dir(self.boost_source.root)
        self.build_env.make_dir(self.output_src_dir)
        dependencies = BOOST_LIBS + BOOST_HEADERS
        print 'Extracting {}'.format(', '.join(dependencies))
        shell('{} {} {}'.format(self.bcp_path, ' '.join(dependencies), self.output_src_dir))
        self.build_env.pop_dir()

    def install_headers(self):
        if os.path.isdir(self.build_env.output_src_dir):
            shutil.rmtree(self.build_env.output_src_dir)
        shutil.copytree(os.path.join(self.output_src_dir, 'boost'), self.build_env.output_src_dir)

    def install(self):
        self.build_bcp()
        self.extract_headers()
        self.install_headers()

#-------------------------------------------------------------------------------
#
# Main
#
#-------------------------------------------------------------------------------

if __name__ == '__main__': 
    
    # Prepare the build folder
    build_env = BuildEnv(os.getcwd())
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

    # Build each platform's targets
    for platform in PLATFORMS:
        for target in tasks[platform]:
            BuildTask(build_env, boost_source, platform, target).run()

    # Package and install the fat libs
    Packager(build_env, boost_source).run()

    # Install the required headers using bcp
    Headers(build_env, boost_source).install()

    # Remove build artifacts
    build_env.cleanup()
