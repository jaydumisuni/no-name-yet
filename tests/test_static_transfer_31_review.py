from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_31_review import run_static_transfer_31_review


def _run(tmp_path: Path, files: dict[str, str]):
    for relative, source in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    return run_static_transfer_31_review(tmp_path, files)


def _roots(result: dict) -> set[str]:
    return {str(item["root_cause"]) for item in result["findings"]}


def test_passive_reader_handoff_requires_failure_resume_path(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "remote/Endpoint.scala": '''
object EndpointWriter {
  final case class StopReading(writer: ActorRef, replyTo: ActorRef)
  final case class StoppedReading(writer: ActorRef)
}
class EndpointReader {
  def receive: Receive = {
    case StopReading(writer, replyTo) =>
      saveState()
      context.become(notReading)
      replyTo ! StoppedReading(writer)
  }
  def notReading: Receive = {
    case StopReading(writer, replyTo) =>
      replyTo ! StoppedReading(writer)
    case InboundPayload(p) => discard(p)
  }
  private def handleDisassociated(info: Info): Unit = ()
}
''',
            "remote/Remoting.scala": '''
class EndpointManager {
  var pendingReadHandoffs = Map[ActorRef, Handle]()
  def receive: Receive = {
    case EndpointWriter.StoppedReading(endpoint) =>
      acceptPendingReader(takingOverFrom = endpoint)
    case Terminated(endpoint) =>
      acceptPendingReader(takingOverFrom = endpoint)
      endpoints.unregisterEndpoint(endpoint)
  }
  private def acceptPendingReader(takingOverFrom: ActorRef): Unit = {
    val endpoint = createEndpoint(writing = false)
    endpoints.registerReadOnlyEndpoint(handle.remoteAddress, endpoint, handle.uid)
  }
}
''',
        },
    )

    assert "reader-suspension-handoff-has-no-failure-resume-path" in _roots(result)


def test_passive_reader_handoff_is_clean_with_identity_bound_resume(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "remote/Endpoint.scala": '''
object EndpointWriter {
  case object ResumeReading
  final case class StopReading(writer: ActorRef, replyTo: ActorRef)
  final case class StoppedReading(writer: ActorRef)
}
class EndpointReader {
  def receive: Receive = {
    case StopReading(writer, replyTo) =>
      context.become(notReading)
      replyTo ! StoppedReading(writer)
  }
  def notReading: Receive = {
    case ResumeReading => context.become(receive)
    case StopReading(writer, replyTo) => replyTo ! StoppedReading(writer)
  }
  private def handleDisassociated(info: Info): Unit = ()
}
''',
            "remote/Remoting.scala": '''
class EndpointManager {
  var pendingReadHandoffs = Map[ActorRef, Handle]()
  var readOnlyReaderResumptions = Map[ActorRef, ResumableReader]()
  def receive: Receive = {
    case EndpointWriter.StoppedReading(endpoint) =>
      acceptPendingReader(endpoint)
    case Terminated(endpoint) =>
      if (!acceptPendingReader(endpoint)) resumeReadingIfNeeded(endpoint)
      endpoints.unregisterEndpoint(endpoint)
  }
  private def acceptPendingReader(endpoint: ActorRef): Boolean = {
    val replacement = createEndpoint(writing = false)
    endpoints.registerReadOnlyEndpoint(handle.remoteAddress, replacement, handle.uid)
    readOnlyReaderResumptions += replacement -> ResumableReader(endpoint, handle.remoteAddress, handle.uid)
    true
  }
  private def resumeReadingIfNeeded(endpoint: ActorRef): Unit =
    readOnlyReaderResumptions.get(endpoint).foreach { state => state.writer ! EndpointWriter.ResumeReading }
}
''',
        },
    )

    assert result["finding_count"] == 0


def test_template_binding_expansion_cannot_scan_joined_host_path(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "installer/lib/project.ex": '''
defmodule Project do
  def join_path(%Project{} = project, location, path)
      when location in [:project, :app, :web] do
    project
    |> Map.fetch!(:"#{location}_path")
    |> Path.join(path)
    |> expand_path_with_bindings(project)
  end

  defp expand_path_with_bindings(path, %Project{} = project) do
    Regex.replace(~r/:[a-zA-Z0-9_]+/, path, fn ":" <> key, _ ->
      project |> Map.fetch!(:"#{key}") |> to_string()
    end)
  end
end
'''
        },
    )

    assert "template-binding-expansion-applied-after-host-path-join" in _roots(result)


def test_template_binding_expansion_is_clean_before_host_path_join(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "installer/lib/project.ex": '''
defmodule Project do
  def join_path(%Project{} = project, location, path)
      when location in [:project, :app, :web] do
    base = Map.fetch!(project, :"#{location}_path")
    expanded = expand_path_with_bindings(path, project)
    Path.join(base, expanded)
  end

  defp expand_path_with_bindings(path, %Project{} = project) do
    Regex.replace(~r/:[a-zA-Z0-9_]+/, path, fn ":" <> key, _ ->
      project |> Map.fetch!(:"#{key}") |> to_string()
    end)
  end
end
'''
        },
    )

    assert result["finding_count"] == 0


def test_upload_payload_cannot_be_materialized_before_request_conversion(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "Source/Session.swift": '''
final class Session {
    func performUploadRequest(_ request: UploadRequest) {
        do {
            let uploadable = try request.upload.createUploadable()
            rootQueue.async { request.didCreateUploadable(uploadable) }
            performSetupOperations(for: request, convertible: request.convertible)
        } catch {
            request.fail(error)
        }
    }

    func performDownloadRequest(_ request: DownloadRequest) {}

    func performSetupOperations(for request: Request, convertible: URLRequestConvertible) {
        let initialRequest = try convertible.asURLRequest()
        adapter.adapt(initialRequest)
    }
}
'''
        },
    )

    assert "upload-payload-materialized-before-request-conversion-and-adaptation" in _roots(result)


def test_upload_payload_is_clean_when_deferred_until_setup_succeeds(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        {
            "Source/Session.swift": '''
final class Session {
    func performUploadRequest(_ request: UploadRequest) {
        performSetupOperations(for: request, convertible: request.convertible) {
            do {
                let uploadable = try request.upload.createUploadable()
                rootQueue.async { request.didCreateUploadable(uploadable) }
                return true
            } catch {
                request.fail(error)
                return false
            }
        }
    }

    func performDownloadRequest(_ request: DownloadRequest) {}

    func performSetupOperations(for request: Request,
                                convertible: URLRequestConvertible,
                                shouldCreateTask: () -> Bool) {
        let initialRequest = try convertible.asURLRequest()
        adapter.adapt(initialRequest)
        guard shouldCreateTask() else { return }
    }
}
'''
        },
    )

    assert result["finding_count"] == 0
