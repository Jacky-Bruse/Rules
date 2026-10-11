# 运行：python test_merge_rules.py
from merge_rules import drop_covered_domains

rules = {
    'DOMAIN-SUFFIX,qq.com',
    'DOMAIN-SUFFIX,weixin.qq.com',      # 被 qq.com 覆盖
    'DOMAIN,btrace.qq.com',             # 被 qq.com 覆盖
    'DOMAIN,QQ.com',                    # 与 DOMAIN-SUFFIX 同名，被覆盖（大小写无关）
    'DOMAIN-SUFFIX,weixin.qq.com.cn',   # qq.com.cn 不是 qq.com 的子域，保留
    'DOMAIN-SUFFIX,myqq.com',           # 只是字符串结尾相同，保留
    'DOMAIN,wechat.com',                # 无覆盖，保留
    'DOMAIN-KEYWORD,qq.com',            # 非 DOMAIN 类型，保留
    'IP-ASN,132203,no-resolve',
}
assert drop_covered_domains(rules) == {
    'DOMAIN-SUFFIX,qq.com',
    'DOMAIN-SUFFIX,weixin.qq.com.cn',
    'DOMAIN-SUFFIX,myqq.com',
    'DOMAIN,wechat.com',
    'DOMAIN-KEYWORD,qq.com',
    'IP-ASN,132203,no-resolve',
}
print('ok')
