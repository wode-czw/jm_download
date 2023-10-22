from jmcomic import  download_album,create_option

import time
option = create_option('成功的配置.yml')




# 调用下载api需要传入此option
download_album('85250', option)
print(option.dir_rule.base_dir)