# Collaborative Agent Architecture: Design and Practice of Multi-User Sharing and Distributed Collaboration

**Abstract**: With the rapid development of large language model (LLM) technology, agents have evolved from single-machine, single-user tools into core execution units for complex tasks. However, current mainstream Agent systems generally suffer from problems such as single-user exclusivity, resource isolation, and difficulty collaborating, making it hard to meet the needs of team-based, large-scale work. This paper proposes a collaborative Agent architecture that, through multi-node distributed deployment, multi-gateway communication routing, multi-user shared access, and fine-grained permission control, achieves cross-node sharing of Agent resources and multi-user collaboration. This architecture supports multiple users operating the same Agent simultaneously, breaking the traditional single-user barrier of Agents; through node resource collaboration, it achieves sharing and utilization of resources unique to different nodes—for example, dedicated resources such as build environments and test environments can be collaboratively invoked by Agents across nodes; through a gateway communication mechanism, it ensures reliable routing and delivery of messages in a distributed environment. Taking an actual system as an example, this paper explains the design philosophy, core mechanisms, and implementation scheme of this architecture, and conducts a comparative analysis with mainstream systems such as Haijun Code, CodeX, and CodeBuddy, demonstrating its advantages in multi-person collaboration scenarios.

**Keywords**: collaborative Agent; multi-user sharing; distributed architecture; multi-node deployment; permission control; large language model

## 1 Introduction

The breakthrough progress of large language models (LLMs) has given rise to a new generation of automation tools centered on agents. From code generation and defect fixing to complex task orchestration, Agents have demonstrated intelligent decision-making capabilities beyond traditional scripts. Commercial products such as Haijun Code, CodeX, and CodeBuddy have emerged one after another, productizing Agent capabilities and providing developers with powerful programming assistants.

However, existing Agent systems were mostly designed from the outset for single-user scenarios, and their architecture is essentially an exclusive "one person, one Agent" model. This model performs excellently in personal development scenarios, but reveals significant limitations in scenarios such as team collaboration and enterprise-level deployment:

- **Single-user exclusivity**: An Agent instance can only be operated by one user at a time, so team members cannot share the same Agent's work context and execution state;
- **Resource islands**: The Agent runs on a single node and cannot share resources and environments unique to other nodes (such as build environments and test environments), making cross-node collaboration workflows difficult to realize;
- **Lack of collaboration**: There is a lack of communication and coordination mechanisms among multiple users, making it difficult for team members to collaborate in real time on the same task;
- **Coarse-grained management**: There is a lack of unified management and access control of node resources, making it impossible to restrict users' access to specific nodes and Agents.

To address the above problems, this paper proposes a collaborative Agent architecture, whose core design principles include:

1. **Multi-user sharing**: Break down the barrier of single-user exclusivity and support multiple users accessing and operating the same Agent simultaneously, sharing its context and execution state;
2. **Multi-node distributed deployment**: The Agent can be deployed on multiple computing nodes, with cross-node communication and resource sharing achieved through a master gateway;
3. **Multi-gateway communication routing**: Establish a distributed gateway system to achieve reliable routing and delivery of messages, guaranteeing the real-time nature of cross-node collaboration;
4. **Fine-grained permission control**: Based on user identity and node resources, achieve refined access control, ensuring the security of multi-user collaboration.

Taking an actually implemented collaborative Agent system as an example, this paper explains in detail the design and implementation of the above architecture. The system already supports multi-node, multi-gateway, multi-user chat rooms, and access permission control, and has achieved cross-user sharing of Agents.

The remainder of this paper is organized as follows: Section 2 reviews the current state of Agent development and analyzes existing problems; Section 3 proposes the theoretical model of the collaborative Agent architecture; Section 4 introduces the concrete implementation of the HaijunBot system; Section 5 conducts a comparative analysis with mainstream systems; Section 6 summarizes the full text and looks ahead to future work.

## 2 Current State of Agent Development and Problem Analysis

### 2.1 Evolution of Agent Technology

The development of Agent technology has roughly gone through three stages:

**Stage One: Rule-driven**. Early Agents were based on predefined rules and finite state machines, executing fixed-flow tasks. Such systems lacked flexibility and were difficult to handle complex and ever-changing real-world scenarios.

**Stage Two: Tool-augmented**. With the rise of LLMs, Agents began to possess natural language understanding and generation capabilities, able to invoke external tools (code execution, file operations, network requests, etc.) to complete tasks. Representatives of this stage include AutoGPT, MetaGPT, and others, which demonstrated Agents' ability to plan and execute autonomously.

**Stage Three: Productization and collaboration**. Currently, Agents are moving from experimental tools to engineering products. Commercial systems such as Haijun Code, CodeX, and CodeBuddy deeply integrate Agent capabilities into development workflows, providing professional functions such as code generation, defect fixing, and test writing. At the same time, the need for team collaboration has become increasingly prominent, driving Agents to evolve from "fighting alone" to "fighting as a team."

### 2.2 Main Limitations of Existing Systems

Although Agent technology has made considerable progress, existing mainstream systems still have the following core limitations in collaboration scenarios:

#### (1) Single-user exclusive mode

Existing Agent systems (such as Haijun Code, CodeX, and CodeBuddy) essentially adopt an exclusive "one person, one Agent" model. Each Agent instance is bound to a single user, and its conversation history, work context, and execution state are strongly coupled with a specific user. When team members need to share the same Agent, they can only do so by copying configurations or taking turns operating it, resulting in fragmented context, inconsistent state, and low collaboration efficiency.

#### (2) Resource islands and scheduling difficulties

An Agent usually runs on a single computing node, and its computing resources (CPU, GPU, memory) are limited by that node's hardware configuration. In a distributed environment, Agents on different nodes are isolated from each other and cannot share their respective unique resources and environments. For example, Node A has a build environment while Node B has a test environment, but the Agents on the two nodes cannot collaborate to complete the full "build→test" workflow, resulting in resource islands.

#### (3) Lack of collaboration mechanisms

Existing systems lack communication and coordination mechanisms among multiple users. Team members cannot collaborate in real time on the same Agent, cannot share task progress, discuss decision plans, or synchronize execution state. Even if some systems support multiple people online at the same time, they are limited to each person's independent session, unable to achieve true collaborative operation.

#### (4) Insufficient node resource management

In distributed deployment scenarios, existing systems lack the capability for unified management of node resources. Administrators cannot restrict specific users' access to certain nodes, cannot control the range of Agents a user can use, and cannot implement role-based resource allocation policies. This coarse-grained management model poses security risks in multi-tenant environments.

### 2.3 Requirements Analysis for Collaborative Agents

Based on the above analysis, a collaborative Agent system should satisfy the following core requirements:

| Requirement        | Description                                                  |
| ------------------ | ------------------------------------------------------------ |
| Multi-user sharing | The same Agent can be accessed and operated by multiple users simultaneously, with access control implemented through ACL |
| Distributed deployment | The Agent can run on multiple nodes, supporting cross-node communication and resource sharing |
| Permission control | Based on user identity and node resources, implement fine-grained access control |
| Communication mechanism | Provide real-time communication channels between users and between users and Agents |
| Resource management | Support sharing of node-specific resources and cross-node collaboration |

## 3 Design of the Collaborative Agent Architecture

### 3.1 Design Principles

The collaborative Agent architecture follows these design principles:

**(1) Sharing first**. An Agent's context, state, and tool capabilities should be designed as shareable resources, rather than user-private data. Through reasonable isolation mechanisms, data security is guaranteed while sharing.

**(2) Distributed transparency**. The physical deployment location of the Agent is transparent to the user. Users do not need to care which node the Agent runs on; they only need to access it through a unified entry point.

**(3) Least privilege**. With a default-deny principle, users can only access nodes and Agents that are explicitly authorized. The permission granularity should be refined to the operation level.

**(4) Communication decoupling**. Communication between users and Agents, and between Agents and Agents, should go through a unified message routing layer, rather than direct point-to-point connections, to support cross-node collaboration.

### 3.2 Overall Architecture

The collaborative Agent architecture adopts a layered model of "multi-node + multi-gateway + shared Agent," as shown in Figure 1.

```text
┌─────────────────────────────────────────────────────────────┐
│                        User Layer                           │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐        │
│  │User A│  │User B│  │User C│  │User D│  │User E│  ...   │
│  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘        │
└─────┼─────────┼─────────┼─────────┼─────────┼─────────────┘
      │         │         │         │         │
┌─────▼─────────────────────────────────────────────────────┐
│                   Master Gateway                           │
│      User interaction · Message forwarding · Agent mgmt    │
└─────┬─────────────────────┬───────────────────────────────┘
      │                     │
┌─────▼─────────────┐ ┌─────▼─────────────┐ ┌─────▼─────────────┐
│  Sub-gateway 1    │ │  Sub-gateway 2    │ │  Sub-gateway 3    │ ...
│  (Node 1)         │ │  (Node 2)         │ │  (Node 3)         │
│  ┌──────────────┐ │ │  ┌──────────────┐ │ │  ┌──────────────┐ │
│  │ Agent A      │ │ │  │ Agent B      │ │ │  │ Agent C      │ │
│  │ Agent D      │ │ │  │ Agent E      │ │ │  │ Agent F      │ │
│  └──────────────┘ │ │  └──────────────┘ │ │  └──────────────┘ │
└───────────────────┘ └───────────────────┘ └───────────────────┘

Figure 1 Overall architecture of the collaborative Agent
```

This architecture contains three core layers:

- **User layer**: Facing end users, it provides a unified access entry point. Users interact with the system through a Web interface or API, without needing to be aware of the underlying node distribution.
- **Gateway layer**: Adopts a master-slave architecture. The master gateway is responsible for user interaction, message forwarding, and Agent management, while sub-gateways are responsible for message routing and Agent operation on their respective nodes. All user requests are forwarded through the master gateway to the target sub-gateway.
- **Node layer**: Carries the Agent runtime environment. Each node corresponds to a physical server, running one sub-gateway and multiple Agent instances. The concepts of node and gateway are closely associated—the gateway is the means of management, and the node is the physical resource.

### 3.3 Multi-User Sharing Mechanism

Multi-user sharing is the core feature of the collaborative Agent architecture. Its design points include:

**Shared context**: Context information such as the Agent's conversation history, task state, and tool invocation records is stored in a shared storage layer, accessible to all authorized users. When multiple users operate the same Agent simultaneously, the system orders the instructions through a message queue, ensuring the Agent processes them in order.

**Concurrent operations**: Multiple users are supported in sending instructions to the same Agent simultaneously. The system orders and schedules the instructions through a message queue, ensuring the Agent processes them in order. Users can observe the Agent's execution progress and output results in real time.

**Session isolation**: Although the Agent context is shared, each user's session view can be independent. Users can view their own operation history and can also view other users' public operation records, achieving collaborative transparency.

### 3.4 Multi-Node Resource Collaboration

Multi-node deployment solves the problem of limited resources on a single machine; its core lies in achieving sharing and collaboration of node-specific resources, with core mechanisms including:

**Node registration and discovery**: After a new node starts, it registers its own information (IP, port, list of running Agents) with the master gateway, and reports the node's unique resources and environments (such as build environments and test environments). The master gateway maintains a global node resource table, supporting dynamic addition and removal of nodes.

**Agent scheduling**: When a user requests the creation of a new Agent, the master gateway selects an appropriate node for deployment based on the specific resources required by the task (such as build environments and test environments) and the user's preferences. The scheduling strategy supports modes such as resource affinity, ensuring the Agent is deployed on a node possessing the required environment.

**Cross-node communication**: Agents on different nodes can transmit messages to each other through the master gateway. The master gateway is responsible for message routing, forwarding, and reliability assurance, achieving cross-node Agent collaboration.

### 3.5 Permission Control Model

The collaborative Agent architecture adopts a role-based access control (RBAC) model, combined with node resource management:

**User roles**: The system defines roles such as administrator, developer, and guest. Different roles have different operation permissions, such as creating Agents, deleting Agents, modifying configurations, and viewing logs.

**Node-level permissions**: Administrators can restrict specific users' access to certain nodes. For example, nodes in the production environment are only accessible to senior developers, while nodes in the test environment are open to all developers.

**Agent-level permissions**: Each Agent can have an independent access control list (ACL) set, specifying which users can view, operate, or manage that Agent. The Agent's owner has the highest permissions and can authorize other users to collaborate.

**Operation-level permissions**: At the Agent level, permissions can be further refined to operation permissions, such as allowing viewing but prohibiting modification, allowing execution but prohibiting deletion, etc.

### 3.6 Communication Mechanism

The collaborative Agent architecture provides multi-layered communication capabilities:

**User-user communication**: Through chat rooms or private messaging, team members can discuss tasks, share progress, and coordinate the division of work.

**User-Agent communication**: Users interact with Agents through a unified message interface, supporting multiple message types such as text instructions, file uploads, and code snippets.

**Agent-Agent communication**: Agents can communicate through the message routing layer, achieving advanced functions such as task decomposition, result aggregation, and collaborative orchestration. An Agent sends a message to a target Agent through a unified gateway interface; the message is routed by the gateway to the node where the target Agent resides, achieving cross-node Agent collaboration.

**Message routing**: The gateway layer implements message routing and forwarding, supporting multiple modes such as point-to-point, broadcast, and multicast. The master gateway is responsible for global message routing, sub-gateways are responsible for message distribution within their node, and the message queue guarantees reliable message delivery and ordered processing.

### 3.7 Collaborative Scheduling Mechanism

The core of multi-person collaboration lies in efficient coordination among Agents, unified scheduling by the gateway, and real-time communication among users. This section explains the key mechanisms that support multi-person collaboration.

**Inter-Agent communication protocol**: Agents transmit messages to each other through a unified gateway interface. The sending Agent calls the gateway's message-sending interface, specifying the target Agent ID and the message content; the gateway determines the node where the target Agent resides according to the Agent routing table and forwards the message to the corresponding node. A reply guideline is automatically appended to the end of the message, telling the receiving Agent how to reply to the sender, forming a complete conversation loop. This mechanism supports two modes, unicast (specifying a single Agent) and broadcast (specifying multiple Agents), meeting the needs of different collaboration scenarios.

**Unified gateway scheduling**: The master gateway, as the unified entry point for all interactions, undertakes responsibilities such as Agent route registration and discovery, message forwarding, and cross-node proxying. Each Agent registers its node information with the master gateway at startup, and the master gateway maintains a global Agent routing table. When a user or Agent needs to access a target Agent, the master gateway queries the routing table to determine the target node and forwards the request to the target Agent through an HTTP or WebSocket proxy. Cross-node access is completely transparent to the caller, without needing to be aware of the Agent's physical location.

**Inter-user collaboration**: The system provides two inter-user communication channels: chat rooms and private chat. Chat rooms support multiple users communicating in real time within the same room, suited to team discussions and task coordination; private chat supports one-to-one communication between users, suited to private discussion of sensitive topics. Inter-user communication and Agent operations are independent of each other, so users can communicate with other users while operating an Agent, achieving a "discuss while operating" collaboration mode.

**Message sequence and ordering guarantee**: When multiple users send instructions to the same Agent simultaneously, the gateway maintains an independent message sequence number for each Agent, ensuring messages are processed in the order they arrive. This mechanism avoids state confusion caused by concurrent operations and guarantees the consistency of Agent execution results.

In addition, the system also provides auxiliary capabilities such as session recovery and scheduled tasks, supporting the persistence and automated scheduling of Agent state, further enhancing collaboration efficiency.

## 4 System Implementation

### 4.1 System Overview

Based on the above architecture design, we have implemented a complete collaborative Agent system. The system is based on multi-node distributed deployment, achieves cross-node collaboration through multi-gateway communication routing, and supports multi-user sharing of Agents and real-time communication. The system's main functional modules include:

- **Node management**: Supports dynamic registration and resource management of nodes;
- **Gateway communication**: Implements message routing, forwarding, and reliability assurance;
- **Agent management**: Supports creation, configuration, copying, deletion, and sharing of Agents;
- **User management**: Supports user authentication, role assignment, and permission control;
- **Chat rooms**: Provides real-time communication channels for multiple users, supporting group chat and private chat;
- **Frontend interface**: Provides an intuitive Web management interface, supporting browsing and operation of Agents.

### 4.2 Multi-Node Distributed Deployment

Corresponding to the theoretical design in Section 3.4, the system implements dynamic registration of nodes and cross-node Agent deployment.

**Node registration**: When a node starts, it registers its own information (IP, port, list of running Agents) and its unique resources and environments (such as build environments and test environments) with the master gateway. The master gateway maintains a global node resource list, supporting dynamic addition and removal of nodes.

**Cross-node Agent deployment**: When a user creates an Agent, they can choose to deploy it to a specified node, or let the system automatically select a node based on the specific resources required by the task. The Agent runs on the target node, but the user accesses it through a unified entry point without needing to be aware of the physical location.

### 4.3 Multi-Gateway Communication Routing

Corresponding to the theoretical designs of the communication mechanism in Section 3.6 and the collaborative scheduling mechanism in Section 3.7, the system adopts a master-slave multi-gateway architecture to implement distributed communication.

**Responsibilities of the master gateway**: The master gateway, as the sole entry point for user interaction, undertakes functions such as user authentication, request distribution, message forwarding, and Agent management. Users interact only with the master gateway, and all data passes through the master gateway. The master gateway itself can also host Agent operation, with functionality no different from a sub-gateway.

**Message routing**: Messages sent by users are routed through the master gateway to the node where the target Agent resides. If the target Agent is within the jurisdiction of a sub-gateway, the master gateway forwards the message to the corresponding sub-gateway; if the target Agent is on the master gateway itself, it is processed directly.

**Cross-gateway communication**: When Agents reside within the jurisdiction of different sub-gateways, messages are relayed through the master gateway to achieve cross-domain communication. Inter-gateway communication uses a reliable transport protocol, ensuring messages are not lost or duplicated.

**Session management**: The master gateway maintains user session state and supports session creation, recovery, and migration. When users switch between different devices, the session state can be migrated seamlessly.

### 4.4 Multi-User Shared Agent

Corresponding to the theoretical design of the multi-user sharing mechanism in Section 3.3, the system implements multi-user collaboration on the same Agent through ACL authorization.

**Agent sharing**: The Agent's owner can share the Agent with other users through an ACL (access control list), specifying whether they can view or operate it. After being granted the corresponding permissions, shared users can view the Agent's state, send instructions, and view execution results.

**Concurrent operations**: Multiple users can send instructions to the same Agent simultaneously. The system orders the instructions through a message queue, ensuring the Agent processes them in order. All users can see the Agent's execution progress and output in real time.

**Context sharing**: The Agent's conversation history and execution state are visible to all authorized users. Newly joined users can quickly understand the task progress without starting from scratch.

**Collaboration transparency**: The system records each user's operation log, and other users can view the operation history, making the collaboration process transparent.

### 4.5 Permissions and Access Control

Corresponding to the theoretical design of the permission control model in Section 3.5, the system implements a multi-layered permission control mechanism:

**User authentication**: Users authenticate their identity through an account password or token. The system supports multiple users online simultaneously, and each user has an independent identity.

**Node-level access control**: Administrators can configure users' access permissions to nodes. Unauthorized users cannot access Agents on specific nodes.

**Agent-level permissions**: Each Agent can have an independent ACL set, specifying which users can view, operate, or manage that Agent. The ACL format is `{"read": [user_id,...], "interact": [user_id,...]}`, and owner and admin users automatically have full control permissions.

**Operation auditing**: The system records all users' operation behaviors, including creation, modification, deletion, execution, etc., facilitating security auditing and problem tracing.

### 4.6 Chat Rooms and Collaboration Assistance

Corresponding to the theoretical designs of the communication mechanism in Section 3.6 and inter-user collaboration in Section 3.7, the system has a built-in chat room function:

**Group chat**: Supports multiple users communicating in real time in the same chat room, allowing discussion of tasks, sharing of progress, and coordination of the division of work.

**Private chat**: Supports one-to-one private communication between users, facilitating private discussion of sensitive topics.

**Message notification**: The system can push notification messages such as Agent state changes and task completion to users, ensuring users are promptly informed of important events.

### 4.7 Collaboration Workflow Example

To intuitively demonstrate the system's collaboration capabilities, the following uses a typical scenario as an example to describe the complete workflow of multi-user collaboration:

**Scenario**: A development team (Users A, B, and C) collaborates to complete the build and test of a project. Node A has a build environment, and Node B has a test environment. The Agents on the two nodes collaborate to complete the full "build→test" workflow.

```text
User A ──┐
User B ──┼──▶ Master Gateway ──▶ Sub-gateway 1 (build Agent) ──▶ Sub-gateway 2 (test Agent)
User C ──┘

Steps:
1. User A creates a build Agent on Node A, and User B creates a test Agent on Node B
2. User A submits the code, and the build Agent executes the build on Node A (build environment)
3. After the build completes, the build Agent forwards the artifacts to the test Agent on Node B through the Master Gateway
4. The test Agent executes tests on Node B (test environment), and User B watches the test progress in real time
5. User C discusses the test results in the chat room and communicates with A and B
6. The test Agent outputs the test report, and the three users review and discuss the modification plan together
7. Based on the discussion results, User A instructs the build Agent to modify the code and rebuild
```

This workflow demonstrates the complete loop of cross-node resource collaboration, multi-user sharing, real-time communication, and collaborative decision-making.

## 5 Comparative Analysis with Mainstream Systems

To evaluate the advantages of the collaborative Agent architecture, this section conducts a comparative analysis of the HaijunBot system with mainstream Agent systems such as Haijun Code, CodeX, and CodeBuddy. The comparison dimensions cover core capabilities such as multi-person collaboration, multi-node deployment, Agent sharing, resource management, and communication means.

### 5.1 Explanation of Comparison Dimensions

| Dimension         | Description                                               |
| ----------------- | --------------------------------------------------------- |
| Multi-person collaboration | Whether it supports multiple users operating the same Agent simultaneously |
| Multi-node deployment | Whether it supports cross-node distributed deployment of Agents |
| Agent sharing     | Whether it supports sharing and authorization of Agents among users |
| Node resource management | Whether it supports node-level resource control and access restrictions |
| Communication means | Whether it provides communication channels between users and between users and Agents |
| Permission control | Whether it supports fine-grained access control          |

### 5.2 Comparison Results

| Capability       | HaijunBot system  | Haijun Code | CodeX      | CodeBuddy  |
| ---------------- | -------------- | ----------- | ---------- | ---------- |
| Multi-person collaboration | ✅ Supported | ❌ Not supported | ❌ Not supported | ❌ Not supported |
| Multi-node deployment | ✅ Supported | ❌ Not supported | ❌ Not supported | ❌ Not supported |
| Agent sharing    | ✅ Supported   | ❌ Not supported | ❌ Not supported | ❌ Not supported |
| Node resource management | ✅ Supported | ❌ Not supported | ❌ Not supported | ❌ Not supported |
| Communication means | ✅ Chat room/private chat | ❌ None | ❌ None | ❌ None |
| Permission control | ✅ Multi-level control | ⚠ Basic permissions | ⚠ Basic permissions | ⚠ Basic permissions |

### 5.3 Comparative Analysis

**Multi-person collaboration**: The HaijunBot system supports multiple users operating the same Agent simultaneously, sharing its context and execution state. Haijun Code, CodeX, and CodeBuddy are all single-user mode, where an Agent instance can only be operated by one user, unable to achieve team collaboration.

**Multi-node deployment**: The HaijunBot system supports cross-node distributed deployment of Agents, achieving sharing and collaboration of node-specific resources. Mainstream systems all run on a single node and cannot leverage the dedicated environments and resources of other nodes.

**Agent sharing**: The HaijunBot system supports sharing and authorization of Agents among users, and authorized users can access and operate shared Agents. Mainstream systems do not have this capability, and Agents are strongly bound to users.

**Node resource management**: The HaijunBot system supports node-level resource control, and administrators can restrict users' access to specific nodes. Mainstream systems lack the concept of a node and cannot achieve cross-node sharing of resources.

**Communication means**: The HaijunBot system has built-in chat room and private chat functions, supporting real-time team communication. Mainstream systems do not provide inter-user communication channels, so collaboration requires external tools.

**Permission control**: The HaijunBot system provides multi-level permission control (node-level, Agent-level, and operation-level). Mainstream systems only provide basic account permission management and cannot achieve fine-grained resource access control.

### 5.4 Discussion

The comparison results show that the HaijunBot system has significant advantages in dimensions such as multi-person collaboration, distributed deployment, and Agent sharing. These advantages stem from its architecture design philosophy of "sharing first, distributed transparency."

In resource collaboration scenarios, the HaijunBot system's advantages are especially prominent. For example, when Node A has a build environment and Node B has a test environment, the HaijunBot system can complete the full "build→test" pipeline through cross-node Agent collaboration; whereas mainstream systems all run on a single node and cannot leverage the dedicated environments of other nodes, so they can only deploy the entire toolchain on the same node, resulting in resource redundancy and collaboration obstacles.

It is worth noting that mainstream systems may offer a more mature experience in single-user scenarios, such as the response speed of code completion and the depth of IDE integration. The collaborative Agent architecture is not intended to replace these systems, but to provide supplementary capabilities for team collaboration scenarios. In actual deployment, the two modes can coexist: individual developers use single-user Agent tools, and teams use a collaborative Agent platform when collaborating.

## 6 Conclusion and Outlook

### 6.1 Conclusion

Aiming at the shortcomings of existing Agent systems in team collaboration scenarios, this paper proposes a collaborative Agent architecture. With multi-user sharing as its core, this architecture achieves cross-user and cross-node sharing of Agent resources through multi-node distributed deployment, multi-gateway communication routing, and fine-grained permission control.

The main contributions include:

1. **Proposing a collaborative Agent architecture model**: Defining a three-layer architecture of user layer, gateway layer, and node layer, and clarifying the responsibilities and interaction mechanisms of each layer;
2. **Designing a multi-user sharing mechanism**: Achieving multi-user collaboration on the same Agent through ACL authorization, concurrent operations, and session isolation;
3. **Implementing multi-node distributed deployment**: Supporting dynamic registration of nodes and cross-node scheduling and communication of Agents;
4. **Establishing multi-layered permission control**: From node-level and Agent-level to operation-level, achieving fine-grained access control;
5. **Providing collaboration assistance tools**: Built-in communication means such as chat rooms and private chat, supporting real-time team collaboration.

### 6.2 Future Work

The collaborative Agent architecture still has many directions worth exploring:

**Intelligent scheduling optimization**: Currently, the Agent's deployment location is specified by the user or automatically selected based on the specific resources required by the task (such as build environments and test environments). In the future, an intelligent scheduling algorithm based on task characteristics (such as computational load, data dependencies, and execution duration) can be introduced, combined with real-time node load and resource utilization, to maximize the efficiency of cross-node resource collaboration.

**Performance and traffic optimization**: Currently, all data transmission uses JSON format, which facilitates debugging and troubleshooting. Once the framework is stable, consider introducing binary protocols (such as Protocol Buffers, MessagePack, etc.) to replace JSON, reducing serialization overhead and network bandwidth consumption, and improving communication efficiency in large-scale collaboration scenarios.

**Security enhancement**: With the popularization of multi-user sharing, security mechanisms need to be further strengthened, including finer-grained operation auditing, abnormal behavior detection, and data encryption.

**Ecosystem integration**: Deep integration with mainstream development tools (IDE, CI/CD, project management platforms) to embed collaborative Agent capabilities into a broader development workflow.

## References

[1] Yao S, Zhao J, Yu D, et al. ReAct: Synergizing Reasoning and Acting in Language Models[C]. International Conference on Learning Representations (ICLR), 2023.

[2] Wang G, Xie Y, Jiang Y, et al. Voyager: An Open-Ended Embodied Agent with Large Language Models[J]. arXiv preprint arXiv:2305.16291, 2023.

[3] Hong S, Zhuge M, Chen J, et al. MetaGPT: Meta Programming for Multi-Agent Collaborative Framework[C]. International Conference on Learning Representations (ICLR), 2024.

[4] Wu Q, Bansal G, Zhang J, et al. AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework[J]. arXiv preprint arXiv:2308.08155, 2023.

[5] Park J S, O'Brien J C, Cai C J, et al. Generative Agents: Interactive Simulacra of Human Behavior[C]. Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology, 2023.

[6] Xi Z, Chen W, Guo X, et al. The Rise and Potential of Large Language Model Based Agents: A Survey[J]. arXiv preprint arXiv:2309.07864, 2023.
