export 'template_disk_cache_types.dart';
export 'template_disk_cache_factory_stub.dart'
    if (dart.library.io) 'template_disk_cache_io.dart'
    if (dart.library.html) 'template_disk_cache_web.dart';
