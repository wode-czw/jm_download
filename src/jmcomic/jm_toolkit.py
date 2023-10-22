from PIL import Image

from .jm_entity import *


class JmcomicText:
    pattern_jm_domain = compile('https://([\w.-]+)')
    pattern_jm_pa_id = compile('(photos?|album)/(\d+)')
    pattern_html_jm_pub_domain = compile('[\w-]+\.\w+/?\w+')

    pattern_html_photo_photo_id = compile('<meta property="og:url" content=".*?/photo/(\d+)/?.*?">')
    pattern_html_photo_scramble_id = compile('var scramble_id = (\d+);')
    pattern_html_photo_name = compile('<title>([\s\S]*?)\|.*</title>')
    # pattern_html_photo_data_original_list = compile('data-original="(.*?)" id="album_photo_.+?"')
    pattern_html_photo_data_original_domain = compile('src="https://(.*?)/media/albums/blank')
    pattern_html_photo_data_original_0 = compile('data-original="(.*?)"[^>]*?id="album_photo[^>]*?data-page="0"')
    pattern_html_photo_tags = compile('<meta name="keywords"[\s\S]*?content="(.*?)"')
    pattern_html_photo_series_id = compile('var series_id = (\d+);')
    pattern_html_photo_sort = compile('var sort = (\d+);')
    pattern_html_photo_page_arr = compile('var page_arr = (.*?);')

    pattern_html_album_album_id = compile('<span class="number">.*?：JM(\d+)</span>')
    pattern_html_album_scramble_id = compile('var scramble_id = (\d+);')
    pattern_html_album_name = compile('<h1 class="book-name" id="book-name">([\s\S]*?)</h1>')
    pattern_html_album_episode_list = compile('data-album="(\d+)">\n *?<li.*?>\n *'
                                              '第(\d+)話\n([\s\S]*?)\n *'
                                              '<[\s\S]*?>(\d+-\d+-\d+).*?')
    pattern_html_album_page_count = compile('<span class="pagecount">.*?:(\d+)</span>')
    pattern_html_album_pub_date = compile('>上架日期 : (.*?)</span>')
    pattern_html_album_update_date = compile('>更新日期 : (.*?)</span>')
    # 作品
    pattern_html_album_works = [
        compile('<span itemprop="author" data-type="works">([\s\S]*?)</span>'),
        compile('<a[^>]*?>(.*?)</a>')
    ]
    # 登場人物
    pattern_html_album_actors = [
        compile('<span itemprop="author" data-type="actor">([\s\S]*?)</span>'),
        compile('<a[^>]*?>(.*?)</a>')
    ]
    # 标签
    pattern_html_album_tags = [
        compile('<span itemprop="genre" data-type="tags">([\s\S]*?)</span>'),
        compile('<a[^>]*?>(.*?)</a>')
    ]
    # 作者
    pattern_html_album_authors = [
        compile('作者： *<span itemprop="author" data-type="author">([\s\S]*?)</span>'),
        compile("<a[^>]*?>(.*?)</a>"),
    ]
    # 點擊喜歡
    pattern_html_album_likes = compile('<span id="albim_likes_\d+">(.*?)</span>')
    # 觀看
    pattern_html_album_views = compile('<span>(.*?)</span> (次觀看|观看次数)')
    # 評論(div)
    pattern_html_album_comment_count = compile('<div class="badge"[^>]*?id="total_video_comments">(\d+)</div>'), 0

    @classmethod
    def parse_to_jm_domain(cls, text: str):
        if text.startswith(JmModuleConfig.PROT):
            return cls.pattern_jm_domain.search(text)[1]

        return text

    @classmethod
    def parse_to_jm_id(cls, text) -> str:
        if isinstance(text, int):
            return str(text)

        ExceptionTool.require_true(isinstance(text, str), f"无法解析jm车号, 参数类型为: {type(text)}")

        # 43210
        if text.isdigit():
            return text

        # Jm43210
        ExceptionTool.require_true(len(text) >= 2, f"无法解析jm车号, 文本太短: {text}")

        # text: JM12341
        c0 = text[0]
        c1 = text[1]
        if (c0 == 'J' or c0 == 'j') and (c1 == 'M' or c1 == 'm'):
            # JM123456
            return text[2:]
        else:
            # https://xxx/photo/412038
            match = cls.pattern_jm_pa_id.search(text)
            ExceptionTool.require_true(match is not None, f"无法解析jm车号, 文本为: {text}")
            return match[2]

    @classmethod
    def analyse_jm_pub_html(cls, html: str, domain_keyword=('jm', 'comic')) -> List[str]:
        domain_ls = cls.pattern_html_jm_pub_domain.findall(html)

        return list(filter(
            lambda domain: any(kw in domain for kw in domain_keyword),
            domain_ls
        ))

    @classmethod
    def analyse_jm_photo_html(cls, html: str) -> JmPhotoDetail:
        return cls.reflect_new_instance(
            html,
            "pattern_html_photo_",
            JmModuleConfig.photo_class()
        )

    @classmethod
    def analyse_jm_album_html(cls, html: str) -> JmAlbumDetail:
        return cls.reflect_new_instance(
            html,
            "pattern_html_album_",
            JmModuleConfig.album_class()
        )

    @classmethod
    def analyse_jm_search_html(cls, html: str) -> JmSearchPage:
        return JmcomicSearchTool.parse_html_to_page(html)

    @classmethod
    def reflect_new_instance(cls, html: str, cls_field_prefix: str, clazz: type):

        def match_field(field_key: str, pattern: Union[Pattern, List[Pattern]], text):

            if isinstance(pattern, list):
                # 如果是 pattern 是 List[re.Pattern]，
                # 取最后一个 pattern 用于 match field，
                # 其他的 pattern 用来给文本缩小范围（相当于多次正则匹配）
                last_pattern = pattern[len(pattern) - 1]
                # 缩小文本
                for i in range(0, len(pattern) - 1):
                    match = pattern[i].search(text)
                    if match is None:
                        return None
                    text = match[0]

                return last_pattern.findall(text)

            if field_key.endswith("_list"):
                return pattern.findall(text)
            else:
                match = pattern.search(text)
                if match is not None:
                    return match[1]
                return None

        field_dict = {}
        pattern_name: str
        for pattern_name, pattern in cls.__dict__.items():
            if not pattern_name.startswith(cls_field_prefix):
                continue

            # 支持如果不匹配，使用默认值
            if isinstance(pattern, tuple):
                pattern, default = pattern
            else:
                default = None

            # 获取字段名和值
            field_name = pattern_name[pattern_name.index(cls_field_prefix) + len(cls_field_prefix):]
            field_value = match_field(field_name, pattern, html)

            if field_value is None:
                if default is None:
                    ExceptionTool.raises_regex(
                        f"文本没有匹配上字段：字段名为'{field_name}'，pattern: [{pattern}]",
                        html=html,
                        pattern=pattern,
                    )
                else:
                    field_value = default

            # 保存字段
            field_dict[field_name] = field_value

        return clazz(**field_dict)

    @classmethod
    def format_url(cls, path, domain):
        assert isinstance(domain, str) and len(domain) != 0

        if domain.startswith(JmModuleConfig.PROT):
            return f'{domain}{path}'

        return f'{JmModuleConfig.PROT}{domain}{path}'

    class DSLReplacer:

        def __init__(self):
            self.dsl_dict: Dict[Pattern, Callable[[Match], str]] = {}

        def parse_dsl_text(self, text) -> str:
            for pattern, replacer in self.dsl_dict.items():
                text = pattern.sub(replacer, text)
            return text

        def add_dsl_and_replacer(self, dsl: str, replacer: Callable[[Match], str]):
            pattern = compile(dsl)
            self.dsl_dict[pattern] = replacer

    @classmethod
    def match_os_env(cls, match: Match) -> str:
        name = match[1]
        value = os.getenv(name, None)
        assert value is not None, f"未配置环境变量: {name}"
        return os.path.abspath(value)

    dsl_replacer = DSLReplacer()

    @classmethod
    def parse_to_abspath(cls, dsl_text: str) -> str:
        path = cls.dsl_replacer.parse_dsl_text(dsl_text)
        return os.path.abspath(path)


# 支持dsl: #{???} -> os.getenv(???)
JmcomicText.dsl_replacer.add_dsl_and_replacer('\$\{(.*?)\}', JmcomicText.match_os_env)


class JmcomicSearchTool:
    # 用来缩减html的长度
    pattern_html_search_shorten_for = compile('<div class="well well-sm">([\s\S]*)<div class="row">')

    # 用来提取搜索页面的的album的信息
    pattern_html_search_album_info_list = compile(
        '<a href="/album/(\d+)/.+"[\s\S]*?'
        'title="(.*?)"[\s\S]*?'
        '(<div class="label-category" style="">'
        '\n(.*)\n</div>\n<div class="label-sub" style=" ">'
        '(.*?)\n<[\s\S]*?)?'
        '<div class="title-truncate tags .*>\n'
        '(<a[\s\S]*?) </div>'
    )

    # 用来查找tag列表
    pattern_html_search_tag_list = compile('<a href=".*?">(.*?)</a>')

    # 查找错误，例如 [错误，關鍵字過短，請至少輸入兩個字以上。]
    pattern_html_search_error = compile('<fieldset>\n<legend>(.*?)</legend>\n<div class=.*?>\n(.*?)\n</div>\n</fieldset>')

    @classmethod
    def parse_html_to_page(cls, html: str) -> JmSearchPage:
        # 检查是否失败
        match = cls.pattern_html_search_error.search(html)
        if match is not None:
            topic, reason = match[1], match[2]
            ExceptionTool.raises_regex(
                f'{topic}: {reason}',
                html=html,
                pattern=cls.pattern_html_search_error,
            )

        # 缩小文本范围
        match = cls.pattern_html_search_shorten_for.search(html)
        if match is None:
            ExceptionTool.raises_regex(
                '未匹配到搜索结果',
                html=html,
                pattern=cls.pattern_html_search_shorten_for,
            )
        html = match[0]

        # 提取结果
        content = []  # content这个名字来源于api版搜索返回值
        album_info_list = cls.pattern_html_search_album_info_list.findall(html)

        for (album_id, title, _, label_category, label_sub, tag_text) in album_info_list:
            tag_list = cls.pattern_html_search_tag_list.findall(tag_text)
            content.append((
                album_id, {
                    'name': title,  # 改成name是为了兼容 parse_api_resp_to_page
                    'tag_list': tag_list
                }
            ))

        return JmSearchPage(content)

    @classmethod
    def parse_api_resp_to_page(cls, data: DictModel) -> JmSearchPage:
        """
        model_data: {
          "search_query": "MANA",
          "total": "177",
          "content": [
            {
              "id": "441923",
              "author": "MANA",
              "description": "",
              "name": "[MANA] 神里绫华5",
              "image": "",
              "category": {
                "id": "1",
                "title": "同人"
              },
              "category_sub": {
                "id": "1",
                "title": "同人"
              }
            }
          ]
        }
        """

        def adapt_item(item: DictModel):
            item: dict = item.src_dict
            item.setdefault('tag_list', [])
            return item

        content = [
            (item.id, adapt_item(item))
            for item in data.content
        ]

        return JmSearchPage(content)


class JmApiAdaptTool:
    """
    本类负责把移动端的api返回值，适配为标准的实体类

    # album
    {
      "id": 123,
      "name": "[狗野叉漢化]",
      "author": [
        "AREA188"
      ],
      "images": [
        "00004.webp"
      ],
      "description": null,
      "total_views": "41314",
      "likes": "918",
      "series": [],
      "series_id": "0",
      "comment_total": "5",
      "tags": [
        "全彩",
        "中文"
      ],
      "works": [],
      "actors": [],
      "related_list": [
        {
          "id": "333718",
          "author": "been",
          "description": "",
          "name": "[been]The illusion of lies（1）[中國語][無修正][全彩]",
          "image": ""
        }
      ],
      "liked": false,
      "is_favorite": false
    }

    # photo
    {
      "id": 413446,
      "series": [
        {
          "id": "487043",
          "name": "第48話",
          "sort": "48"
        }
      ],
      "tags": "慾望 調教 NTL 地鐵 戲劇",
      "name": "癡漢成癮-第2話",
      "images": [
        "00047.webp"
      ],
      "series_id": "400222",
      "is_favorite": false,
      "liked": false
    }
    """
    field_adapter = {
        JmAlbumDetail: [
            'likes',
            'tags',
            'works',
            'actors',
            'related_list',
            'name',
            ('id', 'album_id'),
            ('author', 'authors'),
            ('total_views', 'views'),
            ('comment_total', 'comment_count'),
        ],
        JmPhotoDetail: [
            'name',
            'series_id',
            'tags',
            ('id', 'photo_id'),
            ('images', 'page_arr'),

        ]
    }

    @classmethod
    def parse_entity(cls, data: dict, clazz: type):
        adapter = cls.get_adapter(clazz)

        fields = {}
        for k in adapter:
            if isinstance(k, str):
                v = data[k]
                fields[k] = v
            elif isinstance(k, tuple):
                k, rename_k = k
                v = data[k]
                fields[rename_k] = v

        if issubclass(clazz, JmAlbumDetail):
            cls.post_adapt_album(data, clazz, fields)
        else:
            cls.post_adapt_photo(data, clazz, fields)

        return clazz(**fields)

    @classmethod
    def get_adapter(cls, clazz: type):
        for k, v in cls.field_adapter.items():
            if issubclass(clazz, k):
                return v

        ExceptionTool.raises(f'不支持的类型: {clazz}')

    @classmethod
    def post_adapt_album(cls, data: dict, _clazz: type, fields: dict):
        series = data['series']
        episode_list = []
        for chapter in series:
            chapter = DictModel(chapter)
            # photo_id, photo_index, photo_title, photo_pub_date
            episode_list.append(
                (chapter.id, chapter.sort, chapter.name, None)
            )
        fields['episode_list'] = episode_list
        for it in 'scramble_id', 'page_count', 'pub_date', 'update_date':
            fields[it] = '0'

    @classmethod
    def post_adapt_photo(cls, data: dict, _clazz: type, fields: dict):
        # 1. 获取sort字段，如果data['series']中没有，使用默认值1
        sort = 1
        series: list = data['series']  # series中的sort从1开始
        for chapter in series:
            chapter = DictModel(chapter)
            if int(chapter.id) == int(data['id']):
                sort = chapter.sort
                break

        fields['sort'] = sort
        import random
        fields['data_original_domain'] = random.choice(JmModuleConfig.DOMAIN_API_IMAGE_LIST)


class JmImageTool:

    @classmethod
    def save_resp_img(cls, resp: Any, filepath: str, need_convert=True):
        """
        接收HTTP响应对象，将其保存到图片文件.
        如果需要改变图片的文件格式，比如 .jpg → .png，则需要指定参数 neet_convert=True.
        如果不需要改变图片的文件格式，使用 need_convert=False，可以跳过PIL解析图片，效率更高.

        @param resp: HTTP响应对象
        @param filepath: 图片文件路径
        @param need_convert: 是否转换图片
        """
        if need_convert is False:
            cls.save_directly(resp, filepath)
        else:
            cls.save_image(cls.open_Image(resp.content), filepath)

    @classmethod
    def save_image(cls, image: Image, filepath: str):
        """
        保存图片

        @param image: PIL.Image对象
        @param filepath: 保存文件路径
        """
        image.save(filepath)

    @classmethod
    def save_directly(cls, resp, filepath):
        from common import save_resp_content
        save_resp_content(resp, filepath)

    @classmethod
    def decode_and_save(cls,
                        num: int,
                        img_src: Image,
                        decoded_save_path: str
                        ) -> None:
        """
        解密图片并保存
        @param num: 分割数，可以用 cls.calculate_segmentation_num 计算
        @param img_src: 原始图片
        @param decoded_save_path: 解密图片的保存路径
        """

        # 无需解密，直接保存
        if num == 0:
            img_src.save(decoded_save_path)
            return

        import math
        w, h = img_src.size

        # 创建新的解密图片
        img_decode = Image.new("RGB", (w, h))
        remainder = h % num
        copyW = w
        for i in range(num):
            copyH = math.floor(h / num)
            py = copyH * i
            y = h - (copyH * (i + 1)) - remainder

            if i == 0:
                copyH += remainder
            else:
                py += remainder

            img_decode.paste(
                img_src.crop((0, y, copyW, y + copyH)),
                (0, py, copyW, py + copyH)
            )

        # 保存到新的解密文件
        cls.save_image(img_decode, decoded_save_path)

    @classmethod
    def open_Image(cls, fp: Union[str, bytes]):
        from io import BytesIO
        fp = fp if isinstance(fp, str) else BytesIO(fp)
        return Image.open(fp)

    @classmethod
    def get_num(cls, scramble_id, aid, filename: str) -> int:
        """
        获得图片分割数
        """

        scramble_id = int(scramble_id)
        aid = int(aid)

        if aid < scramble_id:
            return 0
        elif aid < JmModuleConfig.SCRAMBLE_268850:
            return 10
        else:
            import hashlib
            x = 10 if aid < JmModuleConfig.SCRAMBLE_421926 else 8
            s = f"{aid}{filename}"  # 拼接
            s = s.encode()
            s = hashlib.md5(s).hexdigest()
            num = ord(s[-1])
            num %= x
            num = num * 2 + 2
            return num

    @classmethod
    def get_num_by_url(cls, scramble_id, url) -> int:
        """
        获得图片分割数
        """
        return cls.get_num(
            scramble_id,
            aid=JmcomicText.parse_to_jm_id(url),
            filename=of_file_name(url, True),
        )

    @classmethod
    def get_num_by_detail(cls, detail: JmImageDetail) -> int:
        """
        获得图片分割数
        """
        return cls.get_num(detail.scramble_id, detail.aid, detail.img_file_name)


class ExceptionTool:
    """
    抛异常的工具
    1: 能简化 if-raise 语句的编写
    2: 有更好的上下文信息传递方式
    """

    EXTRA_KEY_RESP = 'resp'
    EXTRA_KEY_HTML = 'html'
    EXTRA_KEY_RE_PATTERN = 'pattern'

    @classmethod
    def raises(cls, msg: str, extra: dict = None):
        if extra is None:
            extra = {}

        JmModuleConfig.raise_exception_executor(msg, extra)

    @classmethod
    def raises_regex(cls,
                     msg: str,
                     html: str,
                     pattern: Pattern,
                     ):
        cls.raises(
            msg, {
                cls.EXTRA_KEY_HTML: html,
                cls.EXTRA_KEY_RE_PATTERN: pattern,
            }
        )

    @classmethod
    def raises_resp(cls,
                    msg: str,
                    resp,
                    ):
        cls.raises(
            msg, {
                cls.EXTRA_KEY_RESP: resp
            }
        )

    @classmethod
    def raise_missing(cls,
                      resp,
                      org_req_url=None,
                      ):
        """
        抛出本子/章节的异常
        @param resp: 响应对象
        @param org_req_url: 原始请求url，可不传
        """
        if org_req_url is None:
            org_req_url = resp.url

        req_type = "本子" if "album" in org_req_url else "章节"
        cls.raises_resp((
            f'请求的{req_type}不存在！({org_req_url})\n'
            '原因可能为:\n'
            f'1. id有误，检查你的{req_type}id\n'
            '2. 该漫画只对登录用户可见，请配置你的cookies，或者使用移动端Client（api）\n'
        ), resp)

    @classmethod
    def require_true(cls, case: bool, msg: str):
        if case:
            return

        cls.raises(msg)

    @classmethod
    def replace_old_exception_executor(cls, raises: Callable[[Callable, str, dict], None]):
        old = JmModuleConfig.raise_exception_executor

        def new(msg, extra):
            raises(old, msg, extra)

        JmModuleConfig.raise_exception_executor = new
