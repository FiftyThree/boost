This is a mirror of boost source we use at FiftyThree.

Updating:

1. Download boost source.
2. Build bcp (http://www.boost.org/doc/libs/1_57_0/tools/bcp/doc/html/index.html) via 
```
./bootstrap.sh
./b2 tools/bcp
```
3. OSX binary now is in bin.v2/tools/bcp/darwin-4.2.1/release/link-static/bcp
4. Copy, the syntax is bcp module outputpath

```
bcp  algorithm any bimap bind circular_buffer container current_function exception exception/exception iostreams numeric optional scope_exit uuid variant type_index
```
5. Update the submodule.

