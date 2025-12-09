import pkgutil

import sentry_sdk
import sentry_sdk.integrations

print(f"Sentry SDK Version: {sentry_sdk.VERSION}")
print(f" integrations dir: {dir(sentry_sdk.integrations)}")

# List all submodules in integrations
package = sentry_sdk.integrations
print("Submodules:")
for _importer, modname, _ispkg in pkgutil.iter_modules(package.__path__):
    print(f" - {modname}")
