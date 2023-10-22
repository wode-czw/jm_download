"""
filter(过滤器)是v2.1.12新引入的机制，
利用filter，你可以实现下载时过滤本子/章节/图片，完全控制你要下载的内容。

使用filter的步骤如下：
1. 自定义class，继承JmDownloader，重写filter_iter_objs方法，即:
    class MyDownloader(JmDownloader):
        def filter_iter_objs(self, iter_objs: DownloadIterObjs):
            # 如何重写？参考JmDownloader.filter_iter_objs和下面的示例
            ...

2. 让你的class生效，使用如下代码：
    JmModuleConfig.CLASS_DOWNLOADER = MyDownloader

3. 照常使用下载api:
    download_album(xxx, option)

** 本文件下面的示例只演示步骤1 **

本文件包含如下示例：
- 只下载章节的前三张图
- 只下载本子的特定章节以后的章节


"""

from jmcomic import *


# 示例：只下载章节的前三张图
class First3ImageDownloader(JmDownloader):

    def filter_iter_objs(self, iter_objs: DownloadIterObjs):
        if isinstance(iter_objs, JmPhotoDetail):
            photo: JmPhotoDetail = iter_objs
            # 支持[start,end,step]
            return photo[:3]

        return iter_objs


# 示例：只下载本子的特定章节以后的章节
# 参考：https://github.com/hect0x7/JMComic-Crawler-Python/issues/95
class FindUpdateDownloader(JmDownloader):
    album_after_photo = {
        'xxx': 'yyy'
    }

    def filter_iter_objs(self, iter_objs: DownloadIterObjs):
        if not isinstance(iter_objs, JmAlbumDetail):
            return iter_objs

        return self.find_update(iter_objs)

    # 带入漫画id, 章节id(第x章)，寻找该漫画下第x章节後的所有章节Id
    def find_update(self, album: JmAlbumDetail):
        if album.album_id not in self.album_after_photo:
            return album

        photo_ls = []
        photo_begin = self.album_after_photo[album.album_id]
        is_new_photo = False

        for photo in album:
            if is_new_photo:
                photo_ls.append(photo)

            if photo.photo_id == photo_begin:
                is_new_photo = True

        return photo_ls
