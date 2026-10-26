## 这个 PR 做了什么

<!-- 一句话说明 -->

## 类型

- [ ] 修 Bug
- [ ] 新功能
- [ ] 文档
- [ ] 重构 / 代码质量
- [ ] 新书源适配器

## 关联 Issue

<!-- 例如 Closes #12 -->

## 自查清单

- [ ] `pytest tests -q` 全绿
- [ ] `tznovel --version` 正常
- [ ] 新增功能有对应测试
- [ ] 改了权重常量 → 同步更新 `docs/data/SCORING.md` 与 `tznovel/report/precheck.py`
- [ ] **没有提交任何小说正文**
- [ ] **没有提交 `secrets/` 或任何令牌**
- [ ] `.py` 文件为 **UTF-8 无 BOM**（有 BOM 会 `SyntaxError`）
- [ ] `.ps1` 文件为 **UTF-8 带 BOM**（无 BOM 在 PS 5.1 会乱码）
- [ ] 新书源只适配**公开可免费阅读**的页面

## 测试说明

<!-- 你怎么验证的？跑了哪些命令？ -->

```bash
pytest tests -q
```

## 破坏性变更

- [ ] 有（请说明影响范围与迁移方式）
- [ ] 无

## 备注

<!-- 任何需要 reviewer 知道的事 -->
