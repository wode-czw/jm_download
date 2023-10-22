from .jm_client_impl import *


class DirRule:
    rule_sample = [
        # 根目录 / Album-id / Photo-序号 /
        'Bd_Aid_Pindex',  # 禁漫网站的默认下载方式
        # 根目录 / Album-作者 / Album-标题 / Photo-序号 /
        'Bd_Aauthor_Atitle_Pindex',
        # 根目录 / Photo-序号&标题 /
        'Bd_Pindextitle',
        # 根目录 / Photo-自定义类属性 /
        'Bd_Aauthor_Atitle_Pcustomfield',
        # 需要替换JmModuleConfig.CLASS_ALBUM / CLASS_PHOTO才能让自定义属性生效
    ]

    Detail = Union[JmAlbumDetail, JmPhotoDetail, None]
    RuleFunc = Callable[[Detail], str]
    RuleSolver = Tuple[int, RuleFunc, str]
    RuleSolverList = List[RuleSolver]

    rule_solver_cache: Dict[str, RuleSolver] = {}

    def __init__(self, rule: str, base_dir=None):
        base_dir = JmcomicText.parse_to_abspath(base_dir)
        self.base_dir = base_dir
        self.rule_dsl = rule
        self.solver_list = self.get_role_solver_list(rule, base_dir)

    def deside_image_save_dir(self,
                              album: JmAlbumDetail,
                              photo: JmPhotoDetail,
                              ) -> str:
        path_ls = []
        for solver in self.solver_list:
            try:
                ret = self.apply_rule_solver(album, photo, solver)
            except BaseException as e:
                # noinspection PyUnboundLocalVariable
                jm_debug('dir_rule', f'路径规则"{solver[2]}"的解析出错: {e}, album={album}, photo={photo}')
                raise e

            path_ls.append(str(ret))

        return fix_filepath('/'.join(path_ls), is_dir=True)

    def get_role_solver_list(self, rule_dsl: str, base_dir: str) -> RuleSolverList:
        """
        解析下载路径dsl，得到一个路径规则解析列表
        """

        if '_' not in rule_dsl and rule_dsl != 'Bd':
            ExceptionTool.raises(f'不支持的dsl: "{rule_dsl}"')

        rule_list = rule_dsl.split('_')
        solver_ls: List[DirRule.RuleSolver] = []

        for rule in rule_list:
            if rule == 'Bd':
                solver_ls.append((0, lambda _: base_dir, 'Bd'))
                continue

            rule_solver = self.get_rule_solver(rule)
            if rule_solver is None:
                ExceptionTool.raises(f'不支持的dsl: "{rule}" in "{rule_dsl}"')

            solver_ls.append(rule_solver)

        return solver_ls

    @classmethod
    def get_rule_solver(cls, rule: str) -> Optional[RuleSolver]:
        # 查找缓存
        if rule in cls.rule_solver_cache:
            return cls.rule_solver_cache[rule]

        # 检查dsl
        if not rule.startswith(('A', 'P')):
            return None

        # Axxx or Pyyy
        key = 1 if rule[0] == 'A' else 2
        solve_func = lambda detail, ref=rule[1:]: fix_windir_name(str(detail.get_dirname(ref)))

        # 保存缓存
        rule_solver = (key, solve_func, rule)
        cls.rule_solver_cache[rule] = rule_solver
        return rule_solver

    @classmethod
    def apply_rule_solver(cls, album, photo, rule_solver: RuleSolver) -> str:
        """
        应用规则解析器(RuleSolver)

        @param album: JmAlbumDetail
        @param photo: JmPhotoDetail
        @param rule_solver: Ptitle
        @return: photo.title
        """

        def choose_detail(key):
            if key == 0:
                return None
            if key == 1:
                return album
            if key == 2:
                return photo

        key, func, _ = rule_solver
        detail = choose_detail(key)
        return func(detail)

    @classmethod
    def apply_rule_directly(cls, album, photo, rule: str) -> str:
        return cls.apply_rule_solver(album, photo, cls.get_rule_solver(rule))


class JmOption:

    def __init__(self,
                 dir_rule: Dict,
                 download: Dict,
                 client: Dict,
                 plugin: Dict,
                 filepath=None,
                 ):
        # 版本号
        self.version = JmModuleConfig.JM_OPTION_VER
        # 路径规则配置
        self.dir_rule = DirRule(**dir_rule)
        # 请求配置
        self.client = AdvancedEasyAccessDict(client)
        # 下载配置
        self.download = AdvancedEasyAccessDict(download)
        # 插件配置
        self.plugin = AdvancedEasyAccessDict(plugin)
        # 其他配置
        self.filepath = filepath

        self.call_all_plugin('after_init')

    """
    下面是decide系列方法，为了支持重写和增加程序动态性。
    """

    # noinspection PyUnusedLocal
    def decide_image_batch_count(self, photo: JmPhotoDetail):
        return self.download.threading.image

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def decide_photo_batch_count(self, album: JmAlbumDetail):
        return self.download.threading.photo

    def decide_image_save_dir(self, photo) -> str:
        # 使用 self.dir_rule 决定 save_dir
        save_dir = self.dir_rule.deside_image_save_dir(
            photo.from_album,
            photo
        )

        mkdir_if_not_exists(save_dir)
        return save_dir

    def decide_album_dir(self, album: JmAlbumDetail) -> str:
        """
        该方法目前仅在 plugin-zip 中使用，不建议外部调用
        """
        dir_layer = []
        dir_rule = self.dir_rule
        for rule in dir_rule.rule_dsl.split('_'):
            if rule == 'Bd':
                dir_layer.append(dir_rule.base_dir)
                continue

            if rule[0] == 'A':
                name = dir_rule.apply_rule_directly(album, None, rule)
                dir_layer.append(name)

            if rule[0] == 'P':
                break

        from os.path import join
        return join(*dir_layer)

    def decide_image_suffix(self, image: JmImageDetail):
        # 动图则使用原后缀
        if image.is_gif:
            return image.img_file_suffix

        # 非动图，以配置为先
        return self.download.image.suffix or image.img_file_suffix

    def decide_image_filepath(self, image: JmImageDetail, consider_custom_suffix=True) -> str:
        # 通过拼接生成绝对路径
        save_dir = self.decide_image_save_dir(image.from_photo)
        suffix = self.decide_image_suffix(image) if consider_custom_suffix else image.img_file_suffix
        return os.path.join(save_dir, image.filename_without_suffix + suffix)

    def decide_download_cache(self, _image: JmImageDetail) -> bool:
        return self.download.cache

    def decide_download_image_decode(self, image: JmImageDetail) -> bool:
        # .gif file needn't be decoded
        if image.is_gif:
            return False

        return self.download.image.decode

    """
    下面是创建对象相关方法
    """

    @classmethod
    def default_dict(cls) -> Dict:
        return JmModuleConfig.option_default_dict()

    @classmethod
    def default(cls, proxies=None, domain=None) -> 'JmOption':
        """
        使用默认的 JmOption
        proxies, domain 为常用配置项，为了方便起见直接支持参数配置。
        其他配置项建议还是使用配置文件
        @param proxies: clash; 127.0.0.1:7890; v2ray
        @param domain: 18comic.vip; ["18comic.vip"]
        """
        if proxies is not None or domain is not None:
            return cls.construct({
                'client': {
                    'domain': [domain] if isinstance(domain, str) else domain,
                    'postman': {'meta_data': {'proxies': ProxyBuilder.build_by_str(proxies)}},
                },
            })

        return cls.construct({})

    @classmethod
    def construct(cls, orgdic: Dict, cover_default=True) -> 'JmOption':
        dic = cls.merge_default_dict(orgdic) if cover_default else orgdic

        # debug
        debug = dic.pop('debug', True)
        if debug is False:
            disable_jm_debug()

        # version
        version = dic.pop('version', None)
        if version is None or float(version) >= float(JmModuleConfig.JM_OPTION_VER):
            return cls(**dic)

        # 旧版本option，做兼容

        # 1) 2.0 -> 2.1，并发配置的键名更改了
        dt: dict = dic['download']['threading']
        if 'batch_count' in dt:
            batch_count = dt.pop('batch_count')
            dt['image'] = batch_count

        return cls(**dic)

    def deconstruct(self) -> Dict:
        return {
            'version': self.version,
            'debug': JmModuleConfig.enable_jm_debug,
            'dir_rule': {
                'rule': self.dir_rule.rule_dsl,
                'base_dir': self.dir_rule.base_dir,
            },
            'download': self.download.src_dict,
            'client': self.client.src_dict,
        }

    """
    下面是文件IO方法
    """

    @classmethod
    def from_file(cls, filepath: str) -> 'JmOption':
        dic: dict = PackerUtil.unpack(filepath)[0]
        return cls.construct(dic)

    def to_file(self, filepath=None):
        if filepath is None:
            filepath = self.filepath

        ExceptionTool.require_true(filepath is not None, "未指定JmOption的保存路径")

        PackerUtil.pack(self.deconstruct(), filepath)

    """
    下面是创建客户端的相关方法
    """

    @field_cache("__jm_client_cache__")
    def build_jm_client(self, **kwargs):
        """
        该方法会首次调用会创建JmcomicClient对象，
        然后保存在self.__jm_client_cache__中，
        多次调用`不会`创建新的JmcomicClient对象
        """
        return self.new_jm_client(**kwargs)

    def new_jm_client(self, domain=None, impl=None, **kwargs) -> JmcomicClient:
        # 所有需要用到的 self.client 配置项如下
        postman_conf: dict = self.client.postman.src_dict  # postman dsl 配置
        impl: str = impl or self.client.impl  # client_key
        retry_times: int = self.client.retry_times  # 重试次数
        cache: str = self.client.cache  # 启用缓存

        # domain
        def decide_domain():
            domain_list: Union[List[str], DictModel, dict] = domain if domain is not None \
                else self.client.domain  # 域名

            if not isinstance(domain_list, list):
                domain_list = domain_list.get(impl, [])

            if len(domain_list) == 0:
                domain_list = self.decide_client_domain(impl)

            return domain_list

        domain: List[str] = decide_domain()

        # support kwargs overwrite meta_data
        if len(kwargs) != 0:
            postman_conf['meta_data'].update(kwargs)

        # headers
        meta_data = postman_conf['meta_data']
        if meta_data['headers'] is None:
            meta_data['headers'] = JmModuleConfig.headers(domain[0])

        # postman
        postman = Postmans.create(data=postman_conf)

        # client
        clazz = JmModuleConfig.client_impl_class(impl)
        if clazz == AbstractJmClient or not issubclass(clazz, AbstractJmClient):
            raise NotImplementedError(clazz)
        client = clazz(
            postman,
            retry_times,
            fallback_domain_list=decide_domain(),
        )

        # enable cache
        if cache is True:
            client.enable_cache()

        return client

    # noinspection PyMethodMayBeStatic
    def decide_client_domain(self, client_key: str) -> List[str]:
        def is_client_type(ct: Type[JmcomicClient]):
            if client_key == ct:
                return True

            clazz = JmModuleConfig.client_impl_class(client_key)
            if issubclass(clazz, ct):
                return True

            return False

        if is_client_type(JmApiClient):
            # 移动端
            return JmModuleConfig.DOMAIN_API_LIST

        if is_client_type(JmHtmlClient):
            # 网页端
            return [JmModuleConfig.get_html_domain()]

        ExceptionTool.raises(f'没有配置域名，且是无法识别的client类型: {client_key}')

    @classmethod
    def merge_default_dict(cls, user_dict, default_dict=None):
        """
        深度合并两个字典
        """
        if default_dict is None:
            default_dict = cls.default_dict()

        for key, value in user_dict.items():
            if isinstance(value, dict) and isinstance(default_dict.get(key), dict):
                default_dict[key] = cls.merge_default_dict(value, default_dict[key])
            else:
                default_dict[key] = value
        return default_dict

    # 下面的方法提供面向对象的调用风格

    def download_album(self, album_id):
        from .api import download_album
        download_album(album_id, self)

    def download_photo(self, photo_id):
        from .api import download_photo
        download_photo(photo_id, self)

    # 下面的方法为调用插件提供支持

    def call_all_plugin(self, group: str, **extra):
        plugin_list: List[dict] = self.plugin.get(group, [])
        if plugin_list is None or len(plugin_list) == 0:
            return

        # 保证 jm_plugin.py 被加载
        from .jm_plugin import JmOptionPlugin

        plugin_registry = JmModuleConfig.REGISTRY_PLUGIN
        for pinfo in plugin_list:
            key, kwargs = pinfo['plugin'], pinfo['kwargs']
            plugin_class: Optional[Type[JmOptionPlugin]] = plugin_registry.get(key, None)

            ExceptionTool.require_true(plugin_class is not None, f'[{group}] 未注册的plugin: {key}')

            self.invoke_plugin(plugin_class, kwargs, extra)

    def invoke_plugin(self, plugin_class, kwargs: Any, extra: dict):
        # 保证 jm_plugin.py 被加载
        from .jm_plugin import JmOptionPlugin

        plugin_class: Type[JmOptionPlugin]
        pkey = plugin_class.plugin_key

        try:
            # 检查插件的参数类型
            kwargs = self.fix_kwargs(kwargs)
            # 把插件的配置数据kwargs和附加数据extra合并
            # extra会覆盖kwargs
            if len(extra) != 0:
                kwargs.update(extra)
            # 构建插件对象
            plugin = plugin_class.build(self)
            # 调用插件功能
            jm_debug('plugin.invoke', f'调用插件: [{pkey}]')
            plugin.invoke(**kwargs)
        except JmcomicException as e:
            msg = str(e)
            jm_debug('plugin.exception', f'插件[{pkey}]调用失败，异常信息: {msg}')
            raise e
        except BaseException as e:
            msg = str(e)
            jm_debug('plugin.error', f'插件[{pkey}]运行遇到未捕获异常，异常信息: {msg}')
            raise e

    # noinspection PyMethodMayBeStatic
    def fix_kwargs(self, kwargs) -> Dict[str, Any]:
        """
        kwargs将来要传给方法参数，这要求kwargs的key是str类型，
        该方法检查kwargs的key的类型，如果不是str，尝试转为str，不行则抛异常。
        """
        ExceptionTool.require_true(
            isinstance(kwargs, dict),
            f'插件的kwargs参数必须为dict类型，而不能是类型: {type(kwargs)}'
        )

        kwargs: dict
        new_kwargs: Dict[str, Any] = {}

        for k, v in kwargs.items():
            if isinstance(k, str):
                new_kwargs[k] = v
                continue

            if isinstance(k, (int, float)):
                newk = str(k)
                jm_debug('plugin.kwargs', f'插件参数类型转换: {k} ({type(k)}) -> {newk} ({type(newk)})')
                new_kwargs[newk] = v
                continue

            ExceptionTool.raises(
                f'插件kwargs参数类型有误，'
                f'字段: {k}，预期类型为str，实际类型为{type(k)}'
            )

        return new_kwargs
