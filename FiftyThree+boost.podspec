#
# Be sure to run `pod lib lint FTAnalytics.podspec' to ensure this is a
# valid spec and remove all comments before submitting the spec.
#
# Any lines starting with a # are optional, but encouraged
#
# To learn more about a Podspec see http://guides.cocoapods.org/syntax/podspec.html
#

Pod::Spec.new do |s|
  s.name             = "FiftyThree+boost"
  s.version          = "1.57.0"
  s.summary          = "Boost provides free peer-reviewed portable C++ source libraries."
  s.homepage         = "https://github.com/FiftyThree/boost"
  s.license          = 'LICENSE_1_0.txt'
  s.source           = { :git => "https://github.com/FiftyThree/boost.git", :tag => s.version.to_s }
  s.authors          = "Julian Walker"

  s.platform     = :ios, '7.0'
  s.requires_arc = false

  s.header_mappings_dir = '.'
  s.preserve_paths = 'boost/**/*.{h,hpp}'
  s.user_target_xcconfig = { 'HEADER_SEARCH_PATHS' => '"${PODS_ROOT}/FiftyThree+boost"' }

end
