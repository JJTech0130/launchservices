#import <Foundation/Foundation.h>

extern id _CSStoreCreateWithURL(NSURL *url, NSError **error);
extern id CSStoreCreateMutable(NSError **error);
// dict: not sure, can be nil
// mode: setting 2 will make it update an existing store?
extern void _CSStoreWriteToURL(id store, NSURL *url, NSDictionary *dict, int mode, NSError **error);

typedef void (^EnumerateBlock)(unsigned int arg1, id arg2, const void* arg3, unsigned int arg4, char* arg5);
extern id _CSStoreEnumerateTables(id store, EnumerateBlock block);

extern int _CSStoreGetArrayTable(id store);
extern id _CSStoreCopyDebugDescriptionOfTable(id store, int table, bool someOption);
extern void* CSStoreGetUnit(id store, int table, char *unit, void *arg4);

int main() {
    NSURL *url = [NSURL URLWithString:@"file:///tmp/csstore"];
    NSError *error = nil;
    id store = CSStoreCreateMutable(&error);
    if (!store) {
        NSLog(@"error: %@", error);
        return 1;
    }
    NSLog(@"store: %@", store);
    
    //NSURL *existingURL = [NSURL URLWithString:@"file:///Users/jjtech/Downloads/com.apple.LaunchServices-4031-v2.csstore"];
    NSURL *existingURL = [NSURL URLWithString:@"file:///Users/jjtech/Downloads/com.apple.LaunchServices-3027-v2.csstore"];
    //NSURL *existingURL = [NSURL URLWithString:@"file:///private/var/folders/4n/tqjh0y5n45s_lr7ylncnqsy40000gn/0/com.apple.LaunchServices.dv/com.apple.LaunchServices-5019-v2.csstore"];
    id existingStore = _CSStoreCreateWithURL(existingURL, &error);
    if (!existingStore) {
        NSLog(@"error: %@", error);
        return 1;
    }
    NSLog(@"existingStore: %@", existingStore);
    id out = _CSStoreEnumerateTables(existingStore, ^(unsigned int arg1, id arg2, const void* arg3, unsigned int arg4, char* arg5) {
        NSLog(@"called with %d %@ %p %d '%s'", arg1, arg2, arg3, arg4, arg5);
    });
    //NSLog(@"out: %@", out);

    int arrayTable = _CSStoreGetArrayTable(existingStore);
    if (!arrayTable) {
        NSLog(@"error: %@", error);
        return 1;
    }
    NSLog(@"arrayTable: %d", arrayTable);

    id debugDescription = _CSStoreCopyDebugDescriptionOfTable(existingStore, 80, false);
    if (!debugDescription) {
        NSLog(@"error: %@", error);
        return 1;
    }
    NSLog(@"debugDescription: %@", debugDescription);

    void *arg4 = NULL;
    void *unit = CSStoreGetUnit(existingStore, 80, "", &arg4);
    NSLog(@"arg4: %p, unit: %p", arg4, unit);
    if (!unit) {
        NSLog(@"error: %@", error);
        return 1;
    }
    NSLog(@"unit: %@", unit);


    
    // _CSStoreWriteToURL(store, url, nil, 0, &error);
    // if (error) {
    //     NSLog(@"error: %@", error);
    //     return 1;
    // }
}