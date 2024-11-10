# What is LaunchServices?

LaunchServices is an almost completely undocumented service that is critical for launching applications on macOS and iOS.

# How does LaunchServices work?

`lsd`, the LaunchServices daemon, is responsible for most of the heavy lifting. APIs such as `LSApplicationWorkspace` communicate with it over XPC in order to perform tasks and register applications with it.

`lsd` creates a giant database of all applications on the system, and uses this database to determine which application to launch when a file is opened or a URL is clicked.

# What does this repository contain?
- `samples/`: contains a bunch of files sampled from macOS and iOS that are related to LaunchServices
- `objc/`: contains Objective-C code for using CoreServicesStore.framework on macOS
- `csstore.py`: a command line tool for reversing the LaunchServices database

### How do I use `csstore.py`?
```shell
python ./csstore.py ./samples/com.apple.LaunchServices-5019-v2.csstore dump ./csstore.txt
```

## LaunchServices Database

### Where is the database located?
On macOS, several versions of the database exist, one for each user. You can find their locations like this:

```shell
sudo lsof | grep LaunchServices | grep csstore | grep lsd
```

You should see several database files, for example:
```
lsd         406                  root  txt       REG               1,16   21315584           156310645 /private/var/folders/<RANDOM PATH>/0/com.apple.LaunchServices.dv/com.apple.LaunchServices-<VERSION>-v2.csstore
lsd         619                jjtech  txt       REG               1,16   15007744           156309835 /private/var/folders/<RANDOM PATH>/0/com.apple.LaunchServices.dv/com.apple.LaunchServices-<VERSION>-v2.csstore
lsd         822                    nx  txt       REG               1,16    8519680           148733295 /private/var/folders/<RANDOM PATH>/0/com.apple.LaunchServices.dv/com.apple.LaunchServices-<VERSION>-v2.csstore
```

On iOS 15, the database is located at 
```
/private/var/containers/Data/System/<UUID>/Library/Caches/com.apple.LaunchServices-<VERSION>-v2.csstore
```
With iOS 16, the database was moved to 
```
/private/var/mobile/Containers/Data/InternalDaemon/<UUID>/Library/Caches/com.apple.LaunchServices-<VERSION>-v2.csstore
```

The version number seems to be tied to the macOS/iOS version that created the database, here are the known associations:
- macOS 14.3.1: `5019`
- iOS 15.8.3: `3027`
- iOS 16.1.2: `4031`

### How is the database structured?
As evidenced by the `.csstore` extension, the database is in the proprietary and undocumented `CoreServicesStore` format.
LaunchServices structures the database contents with the following tables:

- `<array>`: ?
- `DB Header`: ?
- `Bundle`: ?
- `Claim`: ?
- `Service`: ?
- `Type`: ?
- `HandlerPref`: ?
- `Container`: ?
- `Alias`: ?
- `Plugin`: ?
- `ExtensionPoint`: ?
- `BindingList`: ?
- `PropertyList`: ?
- `LocalizedString`: ?
- `CanonicalString`: ?
- `BindableKeyMap`: ?
- `UTIBinding`: ?
- `ExtensionBinding`: ?
- `OSTypeBinding`: ?
- `MIMEBinding`: ?
- `NSPasteboardBinding`: ?
- `DeviceModelCodeBinding`: ?
- `BluetoothVendorProductIDBinding`: ?
- `URLSchemeBinding`: ?
- `BundleIDBinding`: ?
- `BundleNameBinding`: ?
- `ActivityTypeBinding`: ?
- `PluginBundleIDBinding`: ?
- `PluginProtocolBinding`: ?
- `PluginUUIDBinding`: ?
- `ExtensionPointIDBinding`: ?
- `<string>`: ?

### How can I inspect the database contents?
On macOS, a handy tool is included: `lsregister`. You can use it to dump the contents of the database in a human readable form:
```shell
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -dump
```

On iOS, a similar tool is located at `/usr/bin/lsdiagnose`

### A note about sysdiagnose
A dump of the database is also included in sysdiganose tarballs. The dump in the sysdiagnose is ends with `.csstoredump`, and it is NOT the raw database, but rather a human readable version that was serialized (why?)

According to the README included with every sysdiagnose...
```
.csstoredump files:
sysdiagnose generates the output of lregister/lsaw in a binary form. To convert
these .csstoredump files to text files, use the following command: 

	lsaw dump --file "PATH TO DUMP FILE" > lsaw.txt

These files can also be opened in CSStore Viewer.
```
...however, I have no idea where one can obtain `lsaw` or `CSStore Viewer`.

