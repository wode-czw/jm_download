from common import *

from .jm_config import *


class JmBaseEntity:

    def save_to_file(self, filepath):
        from common import PackerUtil
        PackerUtil.pack(self, filepath)


class IndexedEntity:
    def getindex(self, index: int):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    def __getitem__(self, item) -> Any:
        if isinstance(item, slice):
            start = item.start or 0
            stop = item.stop or len(self)
            step = item.step or 1
            return [self.getindex(index) for index in range(start, stop, step)]

        elif isinstance(item, int):
            return self.getindex(item)

        else:
            raise TypeError(f"Invalid item type for {self.__class__}")

    def __iter__(self):
        for index in range(len(self)):
            yield self.getindex(index)


class DetailEntity(JmBaseEntity, IndexedEntity):

    @property
    def id(self) -> str:
        raise NotImplementedError

    @property
    def title(self) -> str:
        return getattr(self, 'name')

    def __str__(self):
        return f'{self.__class__.__name__}({self.id}-{self.title})'

    @classmethod
    def __alias__(cls):
        # "JmAlbumDetail" -> "album" (本子)
        # "JmPhotoDetail" -> "photo" (章节)
        cls_name = cls.__name__
        return cls_name[cls_name.index("m") + 1: cls_name.rfind("Detail")].lower()

    def get_dirname(self, ref: str) -> str:
        """
        该方法被 DirDule 调用，用于生成特定层次的文件夹
        通常调用方式如下:
        Atitle -> ref = 'title' -> album.get_dirname(ref)
        该方法需要返回 ref 对应的文件夹名，默认实现直接返回 getattr(self, ref)

        用户可重写此方法，来实现自定义文件夹名

        @param ref: 字段名
        @return: 文件夹名
        """
        return getattr(self, ref)


class JmImageDetail(JmBaseEntity):

    def __init__(self,
                 aid,
                 scramble_id,
                 img_url,
                 img_file_name,
                 img_file_suffix,
                 from_photo=None,
                 query_params=None,
                 index=-1,
                 ) -> None:
        if scramble_id is None or (isinstance(scramble_id, str) and scramble_id == ''):
            from .jm_toolkit import ExceptionTool
            ExceptionTool.raises(f'图片的scramble_id不能为空')

        self.aid: str = str(aid)
        self.scramble_id: str = str(scramble_id)
        self.img_url: str = img_url
        self.img_file_name: str = img_file_name  # without suffix
        self.img_file_suffix: str = img_file_suffix

        self.from_photo: Optional[JmPhotoDetail] = from_photo
        self.query_params: StrNone = query_params
        self.is_exists: bool = False
        self.index = index

    @property
    def filename_without_suffix(self):
        return self.img_file_name

    @property
    def is_gif(self):
        return self.img_file_suffix == '.gif'

    @property
    def download_url(self) -> str:
        """
        图片的下载路径
        与 self.img_url 的唯一不同是，在最后会带上 ?{self.query_params}
        @return: 图片的下载路径
        """
        if self.query_params is None:
            return self.img_url

        return f'{self.img_url}?{self.query_params}'

    @classmethod
    def of(cls,
           photo_id: str,
           scramble_id: str,
           data_original: str,
           from_photo=None,
           query_params=None,
           index=-1,
           ) -> 'JmImageDetail':
        """
        该方法用于创建 JmImageDetail 对象
        """

        # /xxx.yyy
        # ↑   ↑
        # x   y
        x = data_original.rfind('/')
        y = data_original.rfind('.')

        return JmImageDetail(
            aid=photo_id,
            scramble_id=scramble_id,
            img_url=data_original,
            img_file_name=data_original[x + 1:y],
            img_file_suffix=data_original[y:],
            from_photo=from_photo,
            query_params=query_params,
            index=index,
        )

    @property
    def tag(self) -> str:
        """
        this tag is used to print pretty info when debug
        """
        return f'{self.aid}/{self.img_file_name}{self.img_file_suffix} [{self.index + 1}/{len(self.from_photo)}]'


class JmPhotoDetail(DetailEntity):

    def __init__(self,
                 photo_id,
                 name,
                 series_id,
                 sort,
                 tags='',
                 scramble_id='',
                 page_arr=None,
                 data_original_domain=None,
                 data_original_0=None,
                 author=None,
                 from_album=None,
                 ):
        self.photo_id: str = str(photo_id)
        self.scramble_id: str = str(scramble_id)
        self.name: str = str(name).strip()
        self.sort: int = int(sort)
        self._tags: str = tags
        self._series_id: int = int(series_id)

        self._author: StrNone = author
        self.from_album: Optional[JmAlbumDetail] = from_album
        self.index = self.album_index

        # 下面的属性和图片url有关
        if isinstance(page_arr, str):
            import json
            page_arr = json.loads(page_arr)

        # page_arr存放了该photo的所有图片文件名 img_name
        self.page_arr: List[str] = page_arr
        # 图片的cdn域名
        self.data_original_domain: StrNone = data_original_domain
        # 第一张图的URL
        self.data_original_0 = data_original_0

        # 2023-07-14
        # 禁漫的图片url加上了一个参数v，如果没有带上这个参数v，图片会返回空数据
        # 参数v的特点：
        # 1. 值似乎是该photo的更新时间的时间戳，因此所有图片都使用同一个值
        # 2. 值目前在网页端只在photo页面的图片标签的data-original属性出现
        # 这里的模拟思路是，获取到第一个图片标签的data-original，
        # 取出其query参数 → self.data_original_query_params, 该值未来会传递给 JmImageDetail
        self.data_original_query_params = self.get_data_original_query_params(data_original_0)

    @property
    def is_single_album(self) -> bool:
        return self._series_id == 0

    @property
    def tags(self) -> List[str]:
        if self.from_album is not None:
            return self.from_album.tags

        tag_str = self._tags
        if ',' in tag_str:
            # html
            return tag_str.split(',')
        else:
            # api
            return tag_str.split()

    @property
    def indextitle(self):
        return f'第{self.album_index}話 {self.name}'

    @property
    def album_id(self) -> str:
        return self.photo_id if self.is_single_album else str(self._series_id)

    @property
    def album_index(self) -> int:
        """
        返回这个章节在本子中的序号，从1开始
        """

        # 如果是单章本子，JM给的sort为2。
        # 这里返回1比较符合语义定义
        if self.is_single_album and self.sort == 2:
            return 1

        return self.sort

    @property
    def author(self) -> str:
        # 优先使用 from_album
        if self.from_album is not None:
            return self.from_album.author

        if self._author is not None and self._author != '':
            return self._author.strip()

        # 使用默认
        return JmModuleConfig.default_author

    def create_image_detail(self, index) -> JmImageDetail:
        # 校验参数
        length = len(self.page_arr)
        if index >= length:
            raise IndexError(f'image index out of range for photo-{self.photo_id}: {index} >= {length}')

        data_original = self.get_img_data_original(self.page_arr[index])

        return JmModuleConfig.image_class().of(
            self.photo_id,
            self.scramble_id,
            data_original,
            from_photo=self,
            query_params=self.data_original_query_params,
            index=index,
        )

    def get_img_data_original(self, img_name: str) -> str:
        """
        根据图片名，生成图片的完整请求路径 URL
        例如：img_name = 01111.webp
        返回：https://cdn-msp2.18comic.org/media/photos/147643/01111.webp
        """
        domain = self.data_original_domain

        from .jm_toolkit import ExceptionTool
        ExceptionTool.require_true(domain is not None, f'图片域名为空: {domain}')

        return f'{JmModuleConfig.PROT}{domain}/media/photos/{self.photo_id}/{img_name}'

    # noinspection PyMethodMayBeStatic
    def get_data_original_query_params(self, data_original_0: StrNone) -> str:
        if data_original_0 is None:
            return f'v={time_stamp()}'

        index = data_original_0.rfind('?')
        if index == -1:
            return f'v={time_stamp()}'

        return data_original_0[index + 1:]

    @property
    def id(self):
        return self.photo_id

    def getindex(self, index) -> JmImageDetail:
        return self.create_image_detail(index)

    def __getitem__(self, item) -> Union[JmImageDetail, List[JmImageDetail]]:
        return super().__getitem__(item)

    def __len__(self):
        return len(self.page_arr)

    def __iter__(self) -> Generator[JmImageDetail, None, None]:
        return super().__iter__()


class JmAlbumDetail(DetailEntity):

    def __init__(self,
                 album_id,
                 scramble_id,
                 name,
                 episode_list,
                 page_count,
                 pub_date,
                 update_date,
                 likes,
                 views,
                 comment_count,
                 works,
                 actors,
                 authors,
                 tags,
                 related_list=None,
                 ):
        self.album_id: str = str(album_id)
        self.scramble_id: str = str(scramble_id)
        self.name: str = name
        self.page_count: int = int(page_count)  # 总页数
        self.pub_date: str = pub_date  # 发布日期
        self.update_date: str = update_date  # 更新日期

        self.likes: str = likes  # [1K] 點擊喜歡
        self.views: str = views  # [40K] 次觀看
        self.comment_count: int = int(comment_count)  # 评论数
        self.works: List[str] = works  # 作品
        self.actors: List[str] = actors  # 登場人物
        self.tags: List[str] = tags  # 標籤
        self.authors: List[str] = authors  # 作者

        # 有的 album 没有章节，则自成一章。
        episode_list: List[Tuple[str, str, str, str]]
        if len(episode_list) == 0:
            # photo_id, photo_index, photo_title, photo_pub_date
            episode_list = [(album_id, "1", name, pub_date)]
        else:
            episode_list = self.distinct_episode(episode_list)

        self.episode_list = episode_list
        self.related_list = related_list

    @property
    def author(self):
        """
        作者
        禁漫本子的作者标签可能有多个，全部作者请使用字段 self.author_list
        """
        if len(self.authors) >= 1:
            return self.authors[0]

        return JmModuleConfig.default_author

    @property
    def id(self):
        return self.album_id

    @staticmethod
    def distinct_episode(episode_list: list):
        """
        去重章节
        photo_id, photo_index, photo_title, photo_pub_date
        """
        episode_list.sort(key=lambda e: int(e[1]))  # 按照photo_index排序
        ret = [episode_list[0]]

        for i in range(1, len(episode_list)):
            if ret[-1][1] != episode_list[i][1]:
                ret.append(episode_list[i])

        return ret

    def create_photo_detail(self, index) -> Tuple[JmPhotoDetail, Tuple]:
        # 校验参数
        length = len(self.episode_list)

        if index >= length:
            raise IndexError(f'photo index out of range for album-{self.album_id}: {index} >= {length}')

        # ('212214', '81', '94 突然打來', '2020-08-29')
        pid, pindex, pname, _pub_date = self.episode_list[index]

        photo = JmModuleConfig.photo_class()(
            photo_id=pid,
            scramble_id=self.scramble_id,
            name=pname,
            series_id=self.album_id,
            sort=pindex,
            from_album=self,
        )

        return photo, (self.episode_list[index])

    def getindex(self, item) -> JmPhotoDetail:
        return self.create_photo_detail(item)[0]

    def __getitem__(self, item) -> Union[JmPhotoDetail, List[JmPhotoDetail]]:
        return super().__getitem__(item)

    def __len__(self):
        return len(self.episode_list)

    def __iter__(self) -> Generator[JmPhotoDetail, None, None]:
        return super().__iter__()


class JmSearchPage(JmBaseEntity, IndexedEntity):
    ContentItem = Tuple[str, Dict[str, Any]]

    def __init__(self, content: List[ContentItem]):
        # [
        #   album_id, {title, tag_list, ...}
        # ]
        self.content = content

    def iter_id(self) -> Generator[str, None, None]:
        """
        返回 album_id 的迭代器
        """
        for aid, ainfo in self.content:
            yield aid

    def iter_id_title(self) -> Generator[Tuple[str, str], None, None]:
        """
        返回 album_id, album_title 的迭代器
        """
        for aid, ainfo in self.content:
            yield aid, ainfo['name']

    def iter_id_title_tag(self) -> Generator[Tuple[str, str, List[str]], None, None]:
        """
        返回 album_id, album_title, album_tag_list 的迭代器
        """
        for aid, ainfo in self.content:
            yield aid, ainfo['name'], ainfo['tag_list']

    # 下面的方法是对单个album的包装

    @property
    def is_single_album(self):
        return hasattr(self, 'album')

    @property
    def single_album(self) -> JmAlbumDetail:
        return getattr(self, 'album')

    @classmethod
    def wrap_single_album(cls, album: JmAlbumDetail) -> 'JmSearchPage':
        page = JmSearchPage([(
            album.album_id, {
                'name': album.name,
                'tag_list': album.tags,
            }
        )])
        setattr(page, 'album', album)
        return page

    # 下面的方法实现方便的元素访问

    def __len__(self):
        return len(self.content)

    def __iter__(self):
        return self.iter_id_title()

    def __getitem__(self, item) -> Union[ContentItem, List[ContentItem]]:
        return super().__getitem__(item)

    def getindex(self, index: int):
        return self.content[index]
