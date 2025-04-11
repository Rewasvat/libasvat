import copy
import click
import inspect
import fnmatch

_main_commands = []


def main_command_group(cls):
    """Marks this CLASS as a 'main command group'

    Main command groups are listed and initialized by the Main/Root command-group class, and constitutes
    the first level sub-groups from the app's root.
    """
    _main_commands.append(cls)
    return cls


# Source: https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python
class Singleton(type):
    """Metaclass used to create a Singleton class.

    Use it as:
    ```python
    MyClass(metaclass=Singleton):
        pass  # methods as usual
    ```
    Then MyClass and any subclasses will be singletons, meaning when doing instantiations such as `obj = MyClass()`
    it'll alwayss return the same instance.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def class_command(*args, **kwargs):
    """Click Command decorator to mark a method to be setup as a command in DynamicGroup.

    This transforms the method into a click command. Therefore the method will unusable in
    the regular way, since it'll no longer be a function, but instead a click.Command object.

    The method itself is transformed to a static class method and stored as the command's callback.
    However, the DynamicGroup system executes this method passing the object as the first argument
    (thanks to `click.pass_obj`), so the function ends up working as an instance-method, even though
    it's a static method.

    This is a compound decorator - it adds the following decorators to the given function:
    ```python
    @staticmethod
    @click.command(*args, **kwargs)
    @click.pass_obj
    ```
    As such, additional command-related click decorators (such as `click.option` or `click.argument`) can
    be used afterwards to properly setup the command.
    """
    def command_func(f):
        return staticmethod(click.command(*args, **kwargs)(click.pass_obj(f)))
    return command_func


def dynamic_command(name: str = None, **kwargs):
    """Command decorator to setup a method as a command in DynamicGroup.

    This sets up a command WITHOUT affecting the decorated method, so the class API is NOT changed.

    The click Command is created with the given NAME, with HELP as the method's doc-string, and using the `click.pass_obj`
    decorator in the callback (required for DynamicGroup). The command's parameters can be defined by:
    * The `dynamic_argument` and `dynamic_option` decorators (similar to click argument/option decorators).
    * Automatically, via instrospection on the method's signature.

    When using the automatic command parameters via instrospection, the parameters are defined based on the function's parameters,
    following the same order. Each command-param is defined as a `click.Argument`, with the same name, default value and type as
    the matching function-param. If the function-param has a default value, then the command-param is also set as non-required,
    while params without defaults are required.

    Note that the automatic command-parameters method is always used. The `dynamic_argument` and `dynamic_option` decorators
    serve as a way to setup a parameter in a specific way. When using them, these params are created using the decorator value,
    while other non-decorated params are created automatically via introspection.

    NAME is the name of the command in the CLI hierarchy. If ungiven, it defaults to common click name pattern (the function's name, lowered
    and replacing '_' with '-').

    KWARGS is a optional key/value pairs passed along to the `click.Command` constructor.
    """
    def decorator(f):
        info = {}
        if hasattr(f, "_command_info") and f._command_info:
            info = f._command_info

        sig = inspect.signature(f)
        params = []
        for param_key in sig.parameters:
            if param_key == "self":
                continue

            if param_key in info:
                # Function has param info defined via click-like decorators. Use it.
                arg = info[param_key]
            else:
                # No param info available, so build it dinamically with introspection.
                param = sig.parameters[param_key]

                param_type = None
                if param.annotation != param.empty:
                    param_type = param.annotation
                elif param.default != param.empty:
                    param_type = type(param.default)

                param_default = None
                has_default = False
                if param.default != param.empty:
                    has_default = True
                    param_default = param.default

                # We could also use click.Option instead of argument, which also allows the `help` attr. But how to differentiate?
                # `param_decls`, `default`, `required` and `type` attrs are shared between Options and Arguments
                # param_decls is a list of flag/names used to identify the option
                arg = click.Argument(param_decls=[param.name], default=param_default, required=not has_default, type=param_type)
            params.append(arg)

        key = name or f.__name__.lower().replace("_", "-")
        cmd = click.Command(key, callback=click.pass_obj(f), help=f.__doc__, params=params, **kwargs)
        f._command_object = cmd
        return f
    return decorator


def dynamic_argument(param_name: str, **attrs):
    """Sets up a function parameters as a `click.Argument` for the `dynamic_command` decorator.

    This should match a function's parameter, in order to directly configure it as a Argument in
    the generated command.

    PARAM_NAME is the matching function's parameter name, and will be used as the command argument name.

    ATTRS is a dict of values to pass along to the `click.Argument` constructor.
    """
    def decorator(f):
        if not hasattr(f, "_command_info"):
            f._command_info = {}
        f._command_info[param_name] = click.Argument([param_name], **attrs)
        return f
    return decorator


def dynamic_option(param_name: str, *param_decls, **attrs):
    """Sets up a function parameter as a `click.Option` for the `dynamic_command` decorator.

    This should match a function's parameter, in order to directly configure it as a Option in
    the generated command.

    PARAM_NAME is the matching function's parameter name.

    PARAM_DECLS is a list of strings identifying/naming this option on the CLI. Such as a name,
    long flag, short flag values. Example: `--help, -h`.

    ATTRS is a dict of values to pass along to the `click.Option` constructor.
    """
    def decorator(f):
        if not hasattr(f, "_command_info"):
            f._command_info = {"params": {}}
        f._command_info[param_name] = click.Option(param_decls, **attrs)
        return f
    return decorator


def instance_command(*args, **kwargs):
    """Click Command decorator to mark a method to be setup as a command in DynamicGroup.

    This sets up a command WITHOUT affecting the decorated method, so the class API is NOT changed.

    This is the preferred way to setup a command in a class that'll be used in the CLI.

    This works as `click.command`, accepting the same arguments and supporting other command-related
    click-decorators afterwards (such as `click.option` or `click.argument`). Only exception is the
    `click.pass_obj` decorator, which is added automatically due to DynamicGroup requirements.
    """
    def decorator(f):
        cmd = click.command(*args, **kwargs)(click.pass_obj(f))
        f._command_object = cmd
        return f
    return decorator


def sub_group_getter(placeholder_name: str = None, options: list = None, help: str = None):
    """CLI click group decorator to use with DynamicGroup.

    This marks a instance-method of the class as a 'sub-group getter'. That is,
    this method produces other "children" objects which can themselves be used
    as a sub-group of commands for the CLI via DynamicGroup.

    Therefore, with this you can setup sub-groups of commands in an object, that
    are lazily evaluated in the CLI.

    The method is expected to receive a single "name" argument that identifies the object,
    and then returns it or None. Extra arguments are allowed if they have default values.

    OPTIONS is a optional list that defines all available IDs this "group getter" method can
    receive and return a valid object. If this is passed, the options are listed as sub-commands
    in the CLI's help text.

    If OPTIONS is undefined, PLACEHOLDER_NAME is a name used as a wildcard in the CLI's sub-commands
    to denote possible sub-groups accessible from this getter. In this case, the given HELP string (or
    this getter's doc string) is used as the placeholder help text.

    The OPTIONS can also be defined dynamically within the class via the `sub_group_getter.options` decorator.
    Usage:
    ```python
    @sub_group_getter()
    def get_item(self, name):
        for obj in self.items:
            if obj.name == name:
                return obj

    @get_item.options()
    def get_all_item_names(self):
        return [obj.name for obj in self.items]
    ```
    These dynamic option values are added to the given hardcoded OPTIONS list.
    """
    def decorator(f):
        f._command_group = {
            "placeholder_name": placeholder_name,
            "help": help,
            "options": options or [],
            "options_getter": None,
            "hide_options": False,
            "gets_all_objects": False,
        }

        def options_dec(hide_options=False):
            """Sets a method as a 'options getter' for a sub-group (getter) method defined with the `sub_group_getter` decorator.

            This method is expected to receive no arguments and return a list of strings, which should be all the possible options
            the sub-group-getter can receive to return a valid object.

            If HIDE_OPTIONS is True, then the group maintains the list of options for this sub-group, but doesn't show then on HELP
            listings - it only shows the placeholder-name on the help. However, since the list of options still exists within,
            batching commands is supported.
            """
            def internal_options_dec(ff):
                f._command_group["options_getter"] = ff.__name__
                f._command_group["hide_options"] = hide_options
                return ff
            return internal_options_dec
        f.options = options_dec
        return f
    return decorator


def sub_groups(help: str = None):
    """CLI click group decorator to use with DynamicGroup.

    This marks a instance-method of the class as a 'get all sub-groups function'.
    That is, this method should receive no arguments and produces a list of "children" objects
    which will themselves be used as sub-groups of commands for the CLI via DynamicGroup.
    """
    def decorator(f):
        f._command_group = {
            "placeholder_name": None,
            "help": help,
            "options": [],
            "options_getter": None,
            "hide_options": False,
            "gets_all_objects": True,
        }
        return f
    return decorator


def object_identifier(f):
    """Decorator to mark a instance-method as an "ID getter" for that object.

    The ID is used to identify the object in the CLI command hierarchy,
    if no ID/name was given when the object was added to the hierarchy.
    """
    f._object_identifier = True
    return f


def on_setup_group(f):
    """Decorator to mark a instance-method as a `On Setup CLI` method for that object.

    These functions are called by DynamicGroup when initializing the click.Group that
    wraps this instance, and thus should perform any initialization logic on the object
    that is required for its proper behavior when being loaded by the CLI.

    The function is expected to receive the following arguments, in this order:
    * group: The DynamicGroup instance
    * ctx: The click.Context instance

    A class can have multiple on-setup-cli methods, all of them will be called in order.
    """
    f._on_setup_cli = True
    return f


def expand_batch_commands(f):
    """Decorator to mark a instance-method as a `Expand Batch Commands` method for that object.

    This function is called by DynamicGroup when invoking a command with batching enabled.

    Instead of using the base behavior of `fnmatch.filter` to expand a sub-group-name into
    multiple sub-names (thus batching), this marked method will be called instead to do this
    subname => list of subnames processing. Therefore a object can implement its own logic on
    how to expand names for batching sub-commands.

    The method is expected to receive the following arguments, in this order:
    * name: The received sub-group command name to expand.
    * sub_group_names: The list of sub-group names the DynamicGroup knows about (would be used on fnmatch.filter)

    And the method should return a list of sub-group names that are valid to use with at least one of the object's
    sub-group getters.
    """
    f._expand_batch_commands = True
    return f


def group_callback(f):
    """Decorator to mark a instance-method as a `Group Callback` method for that object.

    The group callback method is the method called when the group (if `invoke_without_command` is true), or one of its subcommands, is executed.

    This also uses the `@click.pass_context` decorator on the given method, so that it receives the Click Context object in use.
    With `ctx.invoked_subcommand` one can check if the group is being executed by itself, or if a subcommand is being executed.

    In common Click usage, this is the same as:
    ```python
    @click.group()
    @click.pass_context
    def group_callback(ctx):
        pass # do stuff
    ```
    """
    f._group_callback = True
    return f


def result_callback(f):
    """Decorator to mark a instance-method as a `Result Callback` method for that object.

    The result callback method is called after the group's invoked command is executed. As such it can be used as a
    "Post-Command" callback. It is called with the return value of the subcommand, as well as the parameters as they
    would be passed to the main callback.
    """
    f._result_callback_flag = True
    return f


def support_batch_commands(enable=True):
    """Class-decorator to mark this class as enabling/disabling batch commands according to the ENABLE flag.

    When enabled, using this class with integrated click commands will support "batching" sub-commands together, to
    execute multiple similar commands sequentially in different sub-command-groups in the command hierarchy, by
    separating them with `/` in the command-line.

    Example: if batching is enabled, executing command `clitool stuff foo/bar do-something` will actually
    execute sequentially `clitool stuff foo do-something` and then `clitool stuff bar do-something`.
    In this example `foo` and `bar` are both command-groups themselves that could be implemented in the same integrated
    class, and have the same `do-something` command. While `stuff` is also a integrated class that has batching enabled and
    contains `foo` and `bar` as sub-command-groups (see `@sub_groups`).

    NOTE: batching works best with sub-groups that have different objects with the same or very similar commands.
    This should NOT be used to batch the endpoint command itself (`do_something` in the above example, like `do-something/do-other`),
    because we CANNOT split the arguments between the commands! So each command will receive the same arguments as the others.

    This can be defined on each class (via this decorator) in a class hierarchy to change the value as needed,
    or it can be defined in the object instance itself as the following attribute:
    ```python
    instance._commands_config = {
        "allow_batch_commands": True
    }
    ```
    The top-most value will be used, so: Instance -> Class -> ParentClass -> Grandparent...
    """
    def decorator(cls):
        if not hasattr(cls, "_class_commands_config"):
            cls._class_commands_config = {}
        cls._class_commands_config["allow_batch_commands"] = enable
        return cls
    return decorator


def support_mro_command_check(enable=True):
    """Class-decorator to mark this class as enabling/disabling mro-command checks according to the ENABLE flag.

    When enabled, the class will use MRO-checking to read its integrated commands, instead of the basic/default
    super()-checking.

    MRO-checking checks a overwritten function's MRO (Method Resolution Order) using Python's introspection methods to find
    if, in a base version of the method (in its entire class-hierarchy), it has a click-command. Then, if a base class has a
    command for this method it'll be used for the method in question, updating the command callback to use the actual object class.

    Common super()-checking uses simple super() check on the object to see if its direct base class has a command. This method
    while simpler, doesn't always work with overwritten methods in "large" class-hierarchies (2 or more classes).

    Thus, with MRO-checking enabled, its possible to have a base-class with some integrated commands, and then its derived classes
    (or derived-derived classes, or longer class chains) will still have the same commands, even if they (in any or all points in the
    chain) overwrite the original integrated-command method.

    This can be defined on each class (via this decorator) in a class hierarchy to change the value as needed,
    or it can be defined in the object instance itself as the following attribute:
    ```python
    instance._commands_config = {
        "allow_mro_command_check": True
    }
    ```
    The top-most value will be used, so: Instance -> Class -> ParentClass -> Grandparent..."""
    def decorator(cls):
        if not hasattr(cls, "_class_commands_config"):
            cls._class_commands_config = {}
        cls._class_commands_config["allow_mro_command_check"] = enable
        return cls
    return decorator


def verbose_command_group(verbose=True):
    """Class-decorator to mark this class as using VERBOSE command group.

    Thus, when using objects of this class with integrated click commands (via DynamicGroup), the click group
    will print several debugging messages to the console indicating what is happening.

    This can be defined on each class (via this decorator) in a class hierarchy to change the value as needed,
    or it can be defined in the object instance itself as the following attribute:
    ```python
    instance._commands_config = {
        "verbose": True
    }
    ```
    The top-most value will be used, so: Instance -> Class -> ParentClass -> Grandparent...
    """
    def decorator(cls):
        if not hasattr(cls, "_class_commands_config"):
            cls._class_commands_config = {}
        cls._class_commands_config["verbose"] = verbose
        return cls
    return decorator


def invoke_without_command(enable=True):
    """Class-decorator to enable/disable invoking this class without a command.

    This is the same as defining the `invoke_without_command` attribute on a click.Group, allowing the group
    to be executed without passing on a command.

    This can be defined on each class (via this decorator) in a class hierarchy to change the value as needed,
    or it can be defined in the object instance itself as the following attribute:
    ```python
    instance._commands_config = {
        "invoke_without_command": True,
        "no_args_is_help": False,

    }
    ```
    The top-most value will be used, so: Instance -> Class -> ParentClass -> Grandparent...
    """
    def decorator(cls):
        if not hasattr(cls, "_class_commands_config"):
            cls._class_commands_config = {}
        # Esses 2 atributos (invoke_without_command e no_args_is_help) precisam ser definidos assim pra funcionar
        # É como o click faz na inicialização da classe base do Group
        cls._class_commands_config["invoke_without_command"] = enable
        cls._class_commands_config["no_args_is_help"] = not enable
        return cls
    return decorator


class DynamicGroup(click.Group):
    """Specialized click.Group class to define a hierarchy of CLI commands (from Click) based
    on instance-methods of a generic class.

    This class wraps a given Object (from any class) inside a click.Group instance which can then be used
    in Click's CLI hierarchy. The group's contents are loaded from the object, based on decorators used on
    the object's methods.

    * The object's ID (its 'name' as a group/command in the CLI) can be defined using the `@object_identifier` decorator
    in a "get ID" method. However, not all use-cases require this since some sub-group cases can infer the ID.
    * Commands: to define commands in the group, use the `@class_command()`, `@dynamic_command()` or `@instance_command()` decorators
    on methods that execute command-logic. These can be regular methods used elsewhere by the API or dedicated CLI command-methods.
    * Sub-Groups: to define sub-groups of commands, use the `@sub_group_getter()` or `@sub_groups()` decorators on methods that return
    children objects. These children objects are themselves wrapped with this class in order to be added as sub-groups.
    * Group-specific initialization methods: use the `@on_setup_group` decorator to define methods that are executed when the click.Group
    is initialized, thus allowing for CLI-specific initialization logic to be executed.
    """

    def __init__(self, obj, name=None, obj_type=None, **attrs):
        """* OBJ: the object to be wrapped as a click.Group. This can be None in order to setup a lazy-loading OBJ.
        To do that, this class needs to be derived and the `self.create_object` method needs to be properly implemented.

        * NAME is the optional name of this group in the CLI. This is the name used to call it in the CLI.
        If undefined, a `@object_identifier` method will be searched and executed to get the name. Otherwise,
        if no `@object_identifier` methods exist, then a error will occur since commands need to be named.

        * OBJ_TYPE is the optional type of the object to be wrapped. This is used if OBJ is not defined (None) as a way
        to instantiate (without arguments) the object when it is needed, thus allowing lazy-loading the object without
        requiring to create a derived class of DynamicGroup and overwriting the `create_object` method.
        """
        ######
        self.allow_mro_command_check = False
        """Checks a overwritten function's MRO (Method Resolution Order) using Python's introspection methods to find
        if, in a base version of the method, it has a click-command. Then, if a base class has a command for this method
        it'll be used for the method in question, updating the command callback.

        If false, a simple super() check will be used on a method to see if a base class has a command. This method, while
        simpler, doesn't always work with overwritten methods.

        See also our `get_method_attribute` method.
        """

        if "help" not in attrs:
            if obj is not None:
                attrs["help"] = obj.__class__.__doc__
            elif obj_type is not None:
                attrs["help"] = obj_type.__doc__

        if name is None:
            self.obj = obj
            for key in dir(obj):
                if key.startswith("__"):
                    continue
                value = getattr(obj, key)
                obj_id_flag = self.get_method_attribute(value, "_object_identifier")
                if obj_id_flag:
                    name = value()

        super().__init__(name, **attrs)
        self._setup_group = False
        self.obj = obj
        self.extra_names = {}
        self.is_listing = False
        self.sub_group_getters = []
        self.sub_group_names = []
        self.verbose = False
        self.allow_batch_commands = False
        self.custom_batch_name_expander = None
        if obj is not None:
            self.obj_type = type(obj)
            self.read_config_from_object()
        else:
            self.obj_type = obj_type

    def log(self, msg, fg="white"):
        """Utility method to log a message from this group into the output via click.secho.

        This only works if this instance is with verbose mode activated (`self.verbose = True`). By default, verbose is disabled.
        """
        if self.verbose:
            click.secho(msg, fg=fg)

    def setup_flow_commands(self, ctx: click.Context):
        """Sets up this group, loading the dynamic commands and sub-groups from our wrapped object and adding
        them to the group.

        This is only called once. Initially it checks the object for any dynamic commands/sub-groups to add, and
        then executes any and all 'setup-group' methods from the object.

        See the `class_command`, `dynamic_command` and `instance_command` decorators for help on how to define
        methods as commands in the object.

        See the `sub_group_getter` and `sub_groups` decorators for help on how to define sub-groups of commands
        in the object.
        """
        if self._setup_group:
            return
        self._setup_group = True

        if self.obj is None:
            self.obj = self.create_object(ctx)
            self.read_config_from_object()

        self.log(f"Group {self.name}: Starting Setup with object '{self.obj}'")

        setup_cli_methods = []
        sub_group_infos = []
        obj = self.obj
        for key in dir(obj):
            if key.startswith("__"):
                continue

            value = getattr(obj, key)

            if isinstance(value, click.Command) and value != obj and value != self:
                # Handle hardcoded commands.
                # Sources: @class_command()
                self.add_command(value)

            command_object: click.Command = self.get_method_attribute(value, "_command_object")
            if command_object is not None:
                # Handle dynamic commands
                # Sources: @instance_command(), @dynamic_command()
                if self.allow_mro_command_check:
                    command_object.callback = value
                self.add_command(command_object)

            command_group: dict = self.get_method_attribute(value, "_command_group")
            if command_group is not None:
                # Handle Sub-Groups. These are other "children" objects of our object that are
                # themselves wrapped in DynamicGroup and added to us as sub-groups.
                sub_group_infos.append((value, command_group))

            setup_cli_flag = self.get_method_attribute(value, "_on_setup_cli")
            if setup_cli_flag:
                # Handle On Setup CLI methods. Sources: @on_setup_group
                setup_cli_methods.append(value)

            expand_batch_commands_flag = self.get_method_attribute(value, "_expand_batch_commands")
            if expand_batch_commands_flag:
                self.custom_batch_name_expander = value

            callback_flag = self.get_method_attribute(value, "_group_callback")
            if callback_flag:
                self.callback = click.pass_context(value)

            result_flag = self.get_method_attribute(value, "_result_callback_flag")
            if result_flag:
                self.result_callback()(value)

        for on_setup_cli in setup_cli_methods:
            on_setup_cli(self, ctx)

        for method, group_info in sub_group_infos:
            if group_info["gets_all_objects"]:
                # Handle sources of list of children. Sources: @sub_groups()
                for sub_obj in method():
                    sub_group = self.create_sub_group(sub_obj)
                    self.sub_group_names.append(sub_group.name)
            else:
                # Handle individual children getters. Sources: @sub_group_getter()
                options = group_info["options"]
                options_getter_name = group_info["options_getter"]
                hide_options = group_info["hide_options"]
                if options_getter_name is not None:
                    # Handle @<sub_group_getter>.options()
                    options_getter = getattr(obj, options_getter_name)
                    options += options_getter()

                if len(options) <= 0 or hide_options:
                    sub_name = group_info["placeholder_name"] or key
                    self.extra_names[sub_name] = group_info["help"] or method.__doc__

                for sub_name in options:
                    # Intentionally adding all real sub-group options/names into our list (dont add the placeholder name)
                    self.sub_group_names.append(sub_name)
                    if not hide_options:
                        self.extra_names[sub_name] = group_info["help"] or method.__doc__
                self.sub_group_getters.append(method)

        self.log(f"Group {self.name}: Finished Setup")

    def create_object(self, ctx: click.Context):
        """Called by `setup_flow_commands` to create this instance's wrapped Object, in case it doesn't exist yet (was not passed on construction).

        Therefore, this allows lazy-loading of the wrapped object for a group.

        The default implementation (from DynamicGroup) does and returns nothing. Therefore to implement lazy-loading, this method
        should be overriden, usually through deriving this class and re-implementing this method.
        """
        if self.obj_type is not None:
            return self.obj_type()
        return

    def create_sub_group(self, obj, command_name: str = None):
        """Creates a click sub-group and adds it as a command in this group.

        The created group is a DynamicGroup instance wrapping the given OBJ, and it is the return value of this method.
        The optional COMMAND_NAME argument gives the specific command name this sub-group will have, if undefined then the
        default name DynamicGroup defines will be used (check the class constructor).

        NOTE: this method can be overwritten by derived classes in order to change the sub-group class used.
        This default implementation always uses the DynamicGroup class for any OBJ.
        """
        cmd = DynamicGroup(obj, command_name)
        self.add_command(cmd)
        return cmd

    def get_method_attribute(self, method, attr_name, obj_type=None):
        """Gets an attribute with the given ATTR_NAME from the given METHOD, which should be an attribute/method itself
        from our wrapped object.

        This returns the attribute's value, if it exists, or None otherwise.

        This also checks for the attribute in the parent-method of this obj, using `super()`.

        NOTE: this doesn't work for all cases of overriding decorated-methods from a parent class.
        Problems usually appear in cases of multiple overrides (like `decorated-in-base-class -> override -> override`)

        NOTE2: if `self.allow_mro_command_check` is True, then instead of using `super()` this method will perform a recursive check in
        the parent-method, following the original method's MRO (Method Resolution Order) to properly check amongst all base classes.
        This solves the issue mentioned in the previous NOTE, and thus any command from the class or from base-classes *should* work...
        However, this is a more complex solution that wasn't fully tested...
        """
        if not callable(method):
            return
        value = getattr(method, attr_name, None)
        if value is not None:
            return value

        base_type = None
        if self.allow_mro_command_check:
            if obj_type is not None:
                for base in inspect.getmro(obj_type):
                    if base != obj_type:
                        base_type = base
                        break
            else:
                base_type = type(self.obj)
        else:
            base_type = type(self.obj) if obj_type is None else obj_type

        super_obj = super(base_type, self.obj)
        parent_method = getattr(super_obj, method.__name__, None)
        if parent_method is not None:
            if self.allow_mro_command_check:
                return self.get_method_attribute(parent_method, attr_name, base_type)
            else:
                return getattr(parent_method, attr_name, None)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command:
        self.setup_flow_commands(ctx)

        cmd = super().get_command(ctx, cmd_name)

        self.log(f"Group {self.name}: getting command '{cmd_name}'")
        if cmd is None:
            for group_getter in self.sub_group_getters:
                obj = group_getter(cmd_name)
                if obj is not None:
                    cmd = self.create_sub_group(obj, cmd_name)

        if cmd is None and self.is_listing and cmd_name in self.extra_names:
            return click.Command(cmd_name, callback=None, help=self.extra_names[cmd_name])

        return cmd

    def list_commands(self, ctx: click.Context) -> list[str]:
        self.is_listing = True
        self.setup_flow_commands(ctx)
        extra_names = list(self.extra_names.keys())
        extra_names.sort()
        self.log(f"Group {self.name}: listing commands")
        return super().list_commands(ctx) + extra_names

    def invoke(self, ctx: click.Context):
        self.setup_flow_commands(ctx)

        result = None
        ctx.obj = self.obj
        self.log(f"Group {self.name}: invoking {ctx.protected_args} with args={ctx.args}")
        if not self.allow_batch_commands or len(ctx.protected_args) <= 0:
            # protected-args may be empty - when calling group as a command (invoke_without_command=True)
            return super().invoke(ctx)

        multi_cmds = []
        for name in ctx.protected_args[0].split("/"):
            if name.lower() == "all":
                name = "*"
            name = name.replace("+", "*")
            if self.custom_batch_name_expander:
                values = self.custom_batch_name_expander(name, self.sub_group_names)
            else:
                values = fnmatch.filter(self.sub_group_names, name)
            values = values if len(values) > 0 else [name]
            for subname in values:
                if subname not in multi_cmds:
                    # We dont want duplicated names in multi-cmds, but also want it to maintain the same order of subcommands the user executed.
                    multi_cmds.append(subname)

        self.log(f"Options={self.sub_group_names} // Expanded MultiCmds: {multi_cmds}")

        batch_num = len(multi_cmds)
        rest_protected_args = ctx.protected_args[1:]
        for index, cmd_name in enumerate(multi_cmds):
            if index < batch_num - 1:
                new_ctx = copy.deepcopy(ctx)
            else:
                # Last command in batch we try to execute exactly as click originally processed it.
                # So we use the original Context.
                new_ctx = ctx
            new_ctx.protected_args = [cmd_name] + copy.deepcopy(rest_protected_args)

            try:
                result = super().invoke(new_ctx)
            except click.UsageError as exc:
                # Handling this error here allows us to:
                #   - minimize the printed message to this single one-liner
                #   - allow execution to continue to the rest of the batch commands.
                click.secho(f"{self.name} child-object/command issue: [{exc.cmd.name}] {exc}", fg="red")
        return result

    def resolve_command(self, ctx: click.Context, args: list[str]) -> tuple[str, click.Command, list[str]]:
        """Overwriting click.Group.resolve_command
        This method has no doc on click, so I'm documenting what I've found out.

        This is called by self.invoke to get the cmd-name, args and cmd object itself to be executed, right before executing it.
        Internally it uses self.get_command to get the command object, failing that it returns that "No such command ..." error which
        is printed with command usage/help.

        Notably, ARGS it the actual full list of args for this command and so on. So the first value in ARGS should be the name of the (sub)command
        that is being executed. This is useful since invoke erases ctx.args and ctx.protected_args, and not always we can properly get the
        ctx.invoked_subcommand for some reason.
        """
        self.log(f"Group {self.name}: RESOLVING COMMAND: {args}")
        self.setup_flow_commands(ctx)
        return super().resolve_command(ctx, args)

    def read_config_from_object(self):
        """Updates this DynamicGroup instance's configuration based on our OBJECT.

        The "configuration" consists on some attributes that may be changed to change the behavior of this click command group.
        They are: `allow_mro_command_check`, `verbose` and `allow_batch_commands`.

        The OBJECT may configure these attributes via decorators on its class (or in a parent class), or directly in a
        `_commands_config` dictionary attribute on the object.
        See the `@support_batch_commands`, `@support_mro_command_check` and `@verbose_command_group` decorators for more information.
        """
        config = {}
        classes = inspect.getmro(type(self.obj))  # order top-most -> bottom. So: ObjClass, Parent, Grandparent...
        for cls in reversed(classes):
            cls_config = cls._class_commands_config if hasattr(cls, "_class_commands_config") else {}
            config.update(cls_config)

        obj_config = self.obj._commands_config if hasattr(self.obj, "_commands_config") else {}
        config.update(obj_config)

        supported_values = ["allow_mro_command_check", "verbose", "allow_batch_commands", "invoke_without_command", "no_args_is_help"]
        for var_name in supported_values:
            if var_name in config:
                setattr(self, var_name, config[var_name])
