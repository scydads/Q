from db import QSQLite


class Q(object):

    expression_list = []
    db = QSQLite('test.db')

    @classmethod
    def table_name(cls):
        return cls.__tablename__

    @classmethod
    def field(cls):
        m = {
            'tablename': cls.__tablename__
        }
        for k in dir(cls):
            f = getattr(cls, k)
            if isinstance(f, Field):
                m[f.uuid()] = k
        return m

    @classmethod
    def select(cls, *keys):
        cls.expression_list.append(Node('select', *keys))
        return cls

    @classmethod
    def update(cls, *keys):
        cls.expression_list.append(Node('update', *keys))
        return cls

    @classmethod
    def insert(cls):
        pass

    @classmethod
    def delete(cls, *keys):
        cls.expression_list.append(Node('delete', *keys))
        return cls

    @classmethod
    def where(cls, *keys):
        cls.expression_list.append(Node('where', *keys))
        return cls

    @classmethod
    def order_by(cls):
        pass

    @classmethod
    def group_by(cls):
        pass

    @classmethod
    def execute(cls):
        sql = SQL(cls.expression_list, cls.field()).generate()
        data = cls.db._execute_sql(sql)
        cls.expression_list = []
        # sql.generate()
        return data

    @classmethod
    def generate_sql(cls):
        sql = SQL(cls.expression_list, cls.field()).generate()
        cls.expression_list = []
        return sql

    @classmethod
    def new(cls, form):
        for k, v in form.items():
            attr = getattr(cls, k)
            if attr is None:
                raise
            if not isinstance(attr, Field):
                raise
        n = Node('insert', form)
        cls.expression_list.append(n)
        return cls


class T(object):
    @classmethod
    def count(cls, node):
        func = 'count({})'
        return Function(node, func)

    @classmethod
    def distinct(cls, node):
        func = 'distinct {}'
        return Function(node, func)

    @classmethod
    def max(cls, node):
        func = 'max({})'
        return Function(node, func)

    @classmethod
    def alias(cls, node, name):
        if isinstance(node, Function):
            func = '{} as {}'.format(node.func, _escape(name))
            node.func = func
            return node
        else:
            func = '{} as ' + _escape(name)
            return Function(node, func)


class Node(object):
    def __init__(self, op, *args):
        self.op = op
        self.args = args


class Function(object):
    def __init__(self, node, func):
        self.n = node
        self.func = func


class SQL(object):
    def  __init__(self, expressions, mapper):
        self.expressions = expressions
        self.mapper = mapper


    def generate(self):
        sql = []
        for node in self.expressions:
            if node.op == 'select':
                sub_sql = self._generate_select(node.args)
                sql.append(sub_sql)

            if node.op == 'where':
                sub_sql = self._generate_where(node.args)
                sql.append(sub_sql)

            if node.op == 'insert':
                sub_sql = self._generate_insert(node.args)
                sql.append(sub_sql)

            if node.op == 'update':
                sub_sql = self._generate_update(node.args)
                sql.append(sub_sql)

            if node.op == 'delete':
                sub_sql = self._generate_delete(node.args)
                sql.append(sub_sql)

        return _join_string(sql, ' ')


    def _generate_select(self, nodes):
        tablename = self.mapper.get('tablename')
        if len(nodes) == 0:
            return SQLPattern.select_all.format(tablename)
        else:
            fileds = []
            for node in nodes:
                if isinstance(node, Function):
                    fileds.append(node.func.format(self.mapper.get((node.n.uuid()))))
                else:
                    fileds.append(self.mapper.get((node.uuid())))
            fileds = _join_string(fileds)
            return SQLPattern.select_multi.format(fileds, tablename)

    def _generate_where(self, node):
        if isinstance(node, tuple):
            if len(node) == 0:
                return SQLPattern.where_no
            else:
                return SQLPattern.where_multi.format(self._generate_where(node[0]))
        else:
            if node.op is None:
                return self._generate_where(node.f1)
            if isinstance(node, Field):
                return '{} {} {}'.format(self.mapper.get(node.uuid()), node.op, _escape(node.o))
            else:
                l = self._generate_where(node.f1)
                r = self._generate_where(node.f2)
                return '{} {} {}'.format(l, node.op, r)

    def _generate_insert(self, node):
        form = node[0]
        tablename = self.mapper.get('tablename')

        fileds = _join_string(form.keys())
        values = _join_string(map(_escape, form.values()))
        return SQLPattern.insert.format(tablename, fileds, values)

    def _generate_update(self, node):
        form = node[0]
        tablename = self.mapper.get('tablename')
        es = [SQLPattern.set_element.format(k, _escape(v)) for k, v in form.items()]
        sub_sql = [SQLPattern.update.format(tablename), SQLPattern.set.format(_join_string(es))]
        return _join_string(sub_sql, ' ')

    def _generate_delete(self, node):
        tablename = self.mapper.get('tablename')
        return SQLPattern.delete.format(tablename)


class Expression(object):
    def __init__(self, f1):
        self.f1 = f1
        self.f2 = None
        self.op = None

    def __and__(self, o):
        self.f2 = o
        self.op = 'and'
        return Expression(self)


    def __or__(self, o):
        self.f2 = o
        self.op = 'or'
        return Expression(self)


class Field(object):
    def __init__(self, k=None):
        self.k = k
        self.o = Node
        self.op = None

    def __eq__(self, o):
        self.op = '='
        self.o = o
        return Expression(self)

    def __ne__(self, o):
        self.op = '!='
        self.o = o
        return Expression(self)

    def __le__(self, o):
        self.op = '<'
        self.o = o
        return Expression(self)

    def __gt__(self, o):
        self.op = '>'
        self.o = o
        return Expression(self)

    def __ge__(self, o):
        self.op = '>='
        self.o = o
        return Expression(self)

    def __lt__(self, o):
        self.op = '<='
        self.o = o
        return Expression(self)

    def uuid(self):
        return id(self)


class CharField(Field):
    pass


class IntergerField(Field):
    pass


def _join_string(_list, glue=', '):
    _list = map(str, _list)
    return glue.join(_list)


def _escape(s, template="'{}'"):
    return template.format(s)


class SQLPattern(object):
    select_all = 'select * from {}'
    select_multi = 'select {} from {}'
    where_multi = 'where {}'
    where_no = ''
    insert = 'insert into {} ({}) values ({})'
    update = 'update {}'
    set = 'set {}'
    set_element = '{} = {}'
    delete = 'delete from {}'



if __name__ == '__main__':
    # Q v0.2
    sql = '''
        CREATE TABLE user
          (
             id     INT PRIMARY KEY,
             name   CHAR(50) NOT NULL,
             age    INT NOT NULL,
             gender INT(50),
             phone  CHAR(50)
          );
    '''
    try:
        QSQLite('test.db')._execute_sql(sql)
    except sqlite3.OperationalError:
        pass
    class User(Q):
        __tablename__ = 'user'
        name = CharField()
        age = IntergerField()
        gender = CharField()
        phone = CharField()

    form = dict(
        name='sen',
        age=18,
    )
    for i in range(10):
        User.new(form).execute()
        users = User.select(User.age).where(User.name == 'sen').execute()
        for user in users:
            print(user)

    #
    # sqls = [
    #     {
    #         'comment': 'User.select().execute()',
    #         'sql': User.select().execute(),
    #     },
    #     {
    #         'comment': 'User.select(User.name).execute()',
    #         'sql': User.select(User.name).execute(),
    #     },
    #     {
    #         'comment': 'User.select(User.name, User.age).execute()',
    #         'sql': User.select(User.name, User.age).execute(),
    #     },
    #     {
    #         'comment': "User.select(User.name, User.age).where(User.phone == '136********').execute()",
    #         'sql': User.select(User.name, User.age).where(User.phone == '136********').execute(),
    #     },
    #     {
    #         'comment': "User.select(User.name, User.age).where((User.gender == '男') & (User.age >= 18)).execute()",
    #         'sql': User.select(User.name, User.age).where((User.gender == '男') & (User.age >= 18)).execute(),
    #     },
    #     {
    #         'comment': 'User.select(T.count(User.name)).execute()',
    #         'sql': User.select(T.count(User.name)).execute(),
    #     },
    #     {
    #         'comment': 'User.select(T.distinct(User.name)).execute()',
    #         # 'sql': User.select(T.distinct(User.name)).execute(),
    #     },
    #     {
    #         'comment': 'User.select(T.max(User.age), T.distinct(User.name)).execute()',
    #         # 'sql': User.select(T.max(User.age), T.distinct(User.name)).execute(),
    #     },
    #     {
    #         'comment': 'User.new(form).execute()',
    #         'sql': User.new(form).execute(),
    #     },
    #     {
    #         'comment': 'User.select(T.max(User.age), T.distinct(User.name)).execute()',
    #         # 'sql': User.select(T.max(User.age), T.distinct(User.name)).execute(),
    #     },
    #     {
    #         'comment': "User.update(form).where(User.name != '森').execute()",
    #         'sql': User.update(form).where(User.name != '森').execute(),
    #     },
    #     {
    #         'comment': "User.delete().where(User.name != '森').execute()",
    #         'sql': User.delete().where(User.name != '森').execute(),
    #     },
    #     {
    #         'comment': "User.select(T.alias(T.max(User.age), 'max_age'), T.distinct(User.name)).execute()",
    #         'sql': User.select(T.alias(T.max(User.age), 'max_age'), T.distinct(User.name)).execute(),
    #     },
    #     {
    #         'comment': "User.select(T.alias(User.name, 'user_name')).execute()",
    #         'sql': User.select(T.alias(User.name, 'user_name')).execute(),
    #     },
    # ]
    #
    #
    # template_print = '''
    # {comment}
    # >>>
    # {sql}
    # '''
    # sqls = map(lambda v: template_print.format(**v), sqls)
    # s = _join_string(sqls, glue='\n')
    #
    # template = '''
    # class User(Queryable):
    #     __tablename__ = 'user'
    #     name = CharField()
    #     age = IntergerField()
    #     gender = CharField()
    #     phone = CharField()
    #
    # form = dict(
    #     name='sen',
    #     age=18,
    # )
    #
    # {}
    # '''.format(s)
    # print(template)
    #
    #
    # sqlite = QSQLite('test.db')
    # sql = User.select(T.alias(User.name, 'user_name')).execute()
    # sqlite._execute_sql(sql)
