# 流水线

云原生构建用 `.cnb.yml` 描述流水线，push 或 PR 事件会触发构建。
流水线由若干个 stage 组成，每个 stage 里可以声明多个 job。
